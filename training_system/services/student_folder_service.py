"""
学员文件迁移服务。

当管理员编辑学员的关键字段（training_type、company、name、id_card）时，
负责将该学员在本地磁盘和 COS 上的所有关联文件迁移到新路径，
并协调 DB 路径字段的更新和回滚。
"""

import json
import os
import time
import logging

from services.storage_service import (
    get_base_dir,
    list_dir,
    delete_file,
    _get_backend,
    _get_cos_client,
    _full_cos_key,
)
from services.operation_log_service import create_operation_log

logger = logging.getLogger(__name__)


# ======================== 异常类 ========================

class MigrationError(Exception):
    """迁移失败但已成功回滚。

    调用方收到此异常时，文件系统和 COS 已恢复到迁移前状态，
    应向前端返回错误信息。
    """
    pass


class MigrationRollbackError(Exception):
    """迁移失败且回滚也失败，需人工介入。

    属性:
        completed_ops: 已成功执行但未能回滚的操作列表
        failed_rollbacks: 回滚失败的操作及其错误信息
    """

    def __init__(self, message, completed_ops, failed_rollbacks):
        super().__init__(message)
        self.completed_ops = completed_ops
        self.failed_rollbacks = failed_rollbacks


# ======================== 路径计算工具函数 ========================

_TRAINING_TYPE_MAP = {
    'special_operation': '特种作业',
    'special_equipment': '特种设备',
}


def _training_type_to_chinese(training_type: str) -> str:
    """将 training_type 英文代码转换为中文名称。

    如果传入的已经是中文（如 '特种作业'），直接返回。
    """
    return _TRAINING_TYPE_MAP.get(training_type, training_type)


def _compute_dir_name(training_type: str, company: str, name: str) -> str:
    """计算学员主目录名。

    格式: '{培训类型中文}-{单位名称}-{姓名}'
    示例: '特种作业-阳泉市公司-张三'

    参数:
        training_type: 培训类型（英文代码如 'special_operation' 或中文如 '特种作业'）
        company: 单位名称
        name: 学员姓名

    返回:
        str: 目录名
    """
    training_type_name = _training_type_to_chinese(training_type)
    return f"{training_type_name}-{company}-{name}"


def _compute_file_prefix(id_card: str, name: str) -> str:
    """计算文件名前缀。

    格式: '{身份证号}-{姓名}'
    示例: '123456789012345678-张三'

    参数:
        id_card: 身份证号
        name: 学员姓名

    返回:
        str: 文件名前缀
    """
    return f"{id_card}-{name}"


# ======================== 路径映射计算 ========================

# 学员 DB 记录中所有路径字段
_PATH_FIELDS = (
    'photo_path',
    'diploma_path',
    'id_card_front_path',
    'id_card_back_path',
    'hukou_residence_path',
    'hukou_personal_path',
    'certificate_info_page_path',
    'certificate_records_page_path',
    'training_form_path',
)


def _compute_path_mapping(
    student: dict,
    old_fields: dict,
    new_fields: dict,
) -> list[tuple[str, str]]:
    """计算所有需要迁移的 (old_key, new_key) 对。

    包括：
    - DB 中记录的附件路径（photo_path, diploma_path 等）
    - 报名材料子目录下的所有文件（通过本地 list_dir 枚举）

    对于磁盘上不存在的文件，跳过不报错。

    参数:
        student: 当前数据库中的完整学员记录（dict）
        old_fields: 变更前的关键字段值
            {'training_type': ..., 'company': ..., 'name': ..., 'id_card': ...}
        new_fields: 变更后的关键字段值
            {'training_type': ..., 'company': ..., 'name': ..., 'id_card': ...}

    返回:
        list of (old_relative_path, new_relative_path) 元组
    """
    # 1. 计算旧/新目录名和文件前缀
    old_dir_name = _compute_dir_name(
        old_fields['training_type'], old_fields['company'], old_fields['name']
    )
    new_dir_name = _compute_dir_name(
        new_fields['training_type'], new_fields['company'], new_fields['name']
    )
    old_prefix = _compute_file_prefix(old_fields['id_card'], old_fields['name'])
    new_prefix = _compute_file_prefix(new_fields['id_card'], new_fields['name'])

    mapping: list[tuple[str, str]] = []
    seen_old_paths: set[str] = set()

    # 2. 遍历 DB 中记录的路径字段
    for field in _PATH_FIELDS:
        old_path = student.get(field, '') or ''
        if not old_path:
            continue

        # 计算新路径：替换目录名和文件名前缀
        new_path = _replace_path(old_path, old_dir_name, new_dir_name, old_prefix, new_prefix)

        if new_path != old_path:
            # 检查本地磁盘上是否存在该文件
            abs_path = os.path.join(get_base_dir(), old_path)
            if not os.path.exists(abs_path):
                continue
            mapping.append((old_path, new_path))
            seen_old_paths.add(old_path)

    # 3. 枚举报名材料子目录下的文件
    old_material_dir = f"students/{old_dir_name}/{old_prefix}-报名材料/"
    abs_material_dir = os.path.join(get_base_dir(), old_material_dir.rstrip('/'))

    if os.path.isdir(abs_material_dir):
        # 使用 list_dir 枚举报名材料子目录（递归获取所有文件）
        listing = list_dir(old_material_dir, recursive=True)
        for file_info in listing.get('files', []):
            old_file_key = file_info['key']
            if old_file_key in seen_old_paths:
                continue

            # 计算新路径：替换目录名、子目录名和文件名前缀
            new_file_key = _replace_path(
                old_file_key, old_dir_name, new_dir_name, old_prefix, new_prefix
            )

            if new_file_key != old_file_key:
                mapping.append((old_file_key, new_file_key))
                seen_old_paths.add(old_file_key)

    return mapping


def _replace_path(
    path: str,
    old_dir_name: str,
    new_dir_name: str,
    old_prefix: str,
    new_prefix: str,
) -> str:
    """替换路径中的目录名和文件名前缀。

    路径格式: 'students/{dir_name}/{file_prefix}-xxx.ext'
    或: 'students/{dir_name}/{file_prefix}-报名材料/{file_prefix}-xxx.ext'

    参数:
        path: 原始相对路径
        old_dir_name: 旧目录名
        new_dir_name: 新目录名
        old_prefix: 旧文件名前缀
        new_prefix: 新文件名前缀

    返回:
        str: 替换后的新路径
    """
    # 替换目录名
    new_path = path.replace(
        f"students/{old_dir_name}/",
        f"students/{new_dir_name}/",
        1,
    )
    # 替换文件名前缀（可能出现在子目录名和文件名中）
    new_path = new_path.replace(f"{old_prefix}-", f"{new_prefix}-")
    return new_path

# ======================== 幂等性检测 ========================


def _check_idempotent(
    path_mapping: list[tuple[str, str]],
    student: dict,
) -> bool:
    """幂等性检测：如果新路径已全部存在且旧路径不存在，视为已迁移完成。

    检测逻辑：
    1. 如果 path_mapping 为空，返回 True（无需迁移）。
    2. 检查所有新路径是否已存在（本地磁盘）。
    3. 检查所有旧路径是否已不存在。
    4. 检查 DB 中的路径字段是否已指向新路径。
    5. 如果新旧路径都存在（半成功状态），以新路径为准，清理旧路径残留。

    参数:
        path_mapping: (old_relative_path, new_relative_path) 元组列表
        student: 当前数据库中的完整学员记录

    返回:
        True 表示已迁移完成（跳过实际迁移），False 表示需要执行迁移
    """
    if not path_mapping:
        return True

    base_dir = get_base_dir()

    # 统计各路径的存在状态
    all_new_exist = True
    all_old_missing = True
    both_exist_pairs: list[tuple[str, str]] = []

    for old_key, new_key in path_mapping:
        old_abs = os.path.join(base_dir, old_key)
        new_abs = os.path.join(base_dir, new_key)

        new_exists = os.path.exists(new_abs)
        old_exists = os.path.exists(old_abs)

        if not new_exists:
            all_new_exist = False
        if old_exists:
            all_old_missing = False

        # 记录新旧都存在的对（半成功状态）
        if old_exists and new_exists:
            both_exist_pairs.append((old_key, new_key))

    # 情况 1：新路径全部存在 且 旧路径全部不存在
    # 检查 DB 字段是否已指向新路径
    if all_new_exist and all_old_missing:
        if _db_fields_match_new_paths(path_mapping, student):
            logger.info('幂等性检测：新路径已全部存在且 DB 字段一致，跳过迁移')
            return True

    # 情况 2：半成功状态 - 新旧路径都存在
    # 以新路径为准，清理旧路径残留
    if both_exist_pairs and all_new_exist:
        logger.info(
            f'幂等性检测：检测到半成功状态，{len(both_exist_pairs)} 个文件新旧路径都存在，'
            '以新路径为准，清理旧路径残留'
        )
        for old_key, _new_key in both_exist_pairs:
            try:
                delete_file(old_key)
                logger.info(f'清理旧路径残留: {old_key}')
            except Exception as e:
                logger.warning(f'清理旧路径残留失败: {old_key}, 错误: {e}')
        return True

    # 其他情况：需要执行迁移
    return False


def _db_fields_match_new_paths(
    path_mapping: list[tuple[str, str]],
    student: dict,
) -> bool:
    """检查 DB 中的路径字段是否已指向新路径。

    遍历 path_mapping 中的 (old_key, new_key) 对，
    检查 student 记录中是否有路径字段的值等于 new_key。
    如果所有在 DB 中有记录的路径都已指向新路径，则认为 DB 字段一致。

    参数:
        path_mapping: (old_relative_path, new_relative_path) 元组列表
        student: 当前数据库中的完整学员记录

    返回:
        True 表示 DB 字段已全部指向新路径
    """
    # 构建新路径集合（用于快速查找）
    new_paths_set = {new_key for _, new_key in path_mapping}

    # 检查 DB 中所有路径字段
    for field in _PATH_FIELDS:
        db_value = student.get(field, '') or ''
        if not db_value:
            continue

        # 如果 DB 中的路径值在 path_mapping 的 old_key 中出现，
        # 说明 DB 还指向旧路径，字段不一致
        old_paths_set = {old_key for old_key, _ in path_mapping}
        if db_value in old_paths_set:
            return False

    return True


# ======================== 迁移执行 ========================

def _execute_migration(
    path_mapping: list[tuple[str, str]],
) -> None:
    """执行实际的文件迁移操作。

    按顺序：
    1. 本地 rename（如果 backend 包含 local）
    2. COS copy+delete（如果 backend 包含 cos）

    每步操作成功后记录到 completed_ops 列表，任一步骤失败时
    调用 _rollback(completed_ops) 后抛出 MigrationError。

    参数:
        path_mapping: (old_relative_path, new_relative_path) 元组列表

    异常:
        MigrationError: 迁移失败且回滚完成后抛出
    """
    backend = os.environ.get('STORAGE_BACKEND', 'dual').strip().lower()
    completed_ops: list[dict] = []

    try:
        # 1. 本地 rename（如果 backend 包含 local）
        if backend in ('local', 'dual'):
            base_dir = get_base_dir()
            for old_key, new_key in path_mapping:
                old_abs_path = os.path.join(base_dir, old_key)
                new_abs_path = os.path.join(base_dir, new_key)
                os.renames(old_abs_path, new_abs_path)
                completed_ops.append({
                    'type': 'local_rename',
                    'old_key': old_key,
                    'new_key': new_key,
                })
                logger.info(f'本地迁移: {old_key} -> {new_key}')

        # 2. COS copy+delete（如果 backend 包含 cos）
        if backend in ('cos', 'dual'):
            client, config = _get_cos_client()
            bucket = config['bucket']
            region = config['region']

            for old_key, new_key in path_mapping:
                old_cos_key = _full_cos_key(old_key, config)
                new_cos_key = _full_cos_key(new_key, config)

                # 2a. copy_object: 复制到新 key
                client.copy_object(
                    Bucket=bucket,
                    Key=new_cos_key,
                    CopySource={
                        'Bucket': bucket,
                        'Key': old_cos_key,
                        'Region': region,
                    },
                )
                completed_ops.append({
                    'type': 'cos_copy',
                    'old_key': old_key,
                    'new_key': new_key,
                })
                logger.info(f'COS复制: {old_key} -> {new_key}')

                # 2b. delete_object: 删除旧 key
                client.delete_object(Bucket=bucket, Key=old_cos_key)
                completed_ops.append({
                    'type': 'cos_delete',
                    'old_key': old_key,
                    'new_key': new_key,
                })
                logger.info(f'COS删除旧key: {old_key}')

    except Exception as e:
        logger.error(f'迁移失败: {e}，开始回滚已完成的 {len(completed_ops)} 个操作')
        _rollback(completed_ops)
        raise MigrationError(f'文件迁移失败: {e}') from e


# ======================== 回滚逻辑 ========================

def _rollback(completed_ops: list[dict]) -> None:
    """逆序回滚已完成的操作。

    遍历 completed_ops（逆序），对每个操作执行反向操作：
    - local_rename：将文件从 new_key 移回 old_key
    - cos_copy：删除新 key（copy 的逆操作）
    - cos_delete：从新 key copy 回旧 key（delete 的逆操作）

    如果所有回滚操作均成功，正常返回。
    如果任一回滚操作失败，收集失败信息后抛出 MigrationRollbackError。

    参数:
        completed_ops: 已完成的操作列表，每个元素格式:
            {'type': 'local_rename'|'cos_copy'|'cos_delete',
             'old_key': str, 'new_key': str}

    异常:
        MigrationRollbackError: 回滚过程中有操作失败时抛出
    """
    failed_rollbacks: list[dict] = []
    base_dir = get_base_dir()

    for op in reversed(completed_ops):
        op_type = op['type']
        old_key = op['old_key']
        new_key = op['new_key']

        try:
            if op_type == 'local_rename':
                # 将文件从 new 移回 old
                new_abs_path = os.path.join(base_dir, new_key)
                old_abs_path = os.path.join(base_dir, old_key)
                os.renames(new_abs_path, old_abs_path)
                logger.info(f'回滚 local_rename: {new_key} -> {old_key}')

            elif op_type == 'cos_copy':
                # copy 的逆操作：删除新 key
                client, config = _get_cos_client()
                full_new_key = _full_cos_key(new_key, config)
                client.delete_object(
                    Bucket=config['bucket'],
                    Key=full_new_key,
                )
                logger.info(f'回滚 cos_copy: 删除 {new_key}')

            elif op_type == 'cos_delete':
                # delete 的逆操作：从新 key copy 回旧 key
                client, config = _get_cos_client()
                full_new_key = _full_cos_key(new_key, config)
                full_old_key = _full_cos_key(old_key, config)
                client.copy_object(
                    Bucket=config['bucket'],
                    Key=full_old_key,
                    CopySource={
                        'Bucket': config['bucket'],
                        'Key': full_new_key,
                        'Region': config['region'],
                    },
                )
                logger.info(f'回滚 cos_delete: 从 {new_key} 复制回 {old_key}')

            else:
                logger.warning(f'回滚跳过未知操作类型: {op_type}')

        except Exception as e:
            logger.error(f'回滚失败 [{op_type}] old={old_key} new={new_key}: {e}')
            failed_rollbacks.append({
                'op': op,
                'error': str(e),
            })

    if failed_rollbacks:
        raise MigrationRollbackError(
            f'迁移回滚部分失败，{len(failed_rollbacks)} 个操作未能恢复，需人工介入',
            completed_ops,
            failed_rollbacks,
        )


# ======================== 主入口函数 ========================


def _compute_changed_fields(old_fields: dict, new_fields: dict) -> list[str]:
    """比较旧字段和新字段，返回发生变化的字段名列表。

    参数:
        old_fields: 变更前的关键字段值
        new_fields: 变更后的关键字段值

    返回:
        list[str]: 发生变化的字段名列表，如 ['name', 'company']
    """
    changed = []
    for key in old_fields:
        if old_fields.get(key) != new_fields.get(key):
            changed.append(key)
    return changed


def migrate_student_files(
    student: dict,
    old_fields: dict,
    new_fields: dict,
) -> dict:
    """执行学员文件迁移。

    参数:
        student: 当前数据库中的完整学员记录
        old_fields: 变更前的关键字段值
            {'training_type': ..., 'company': ..., 'name': ..., 'id_card': ...}
        new_fields: 变更后的关键字段值（已 trim）
            {'training_type': ..., 'company': ..., 'name': ..., 'id_card': ...}

    返回:
        dict: 需要更新到 DB 的路径字段映射 {db_key: new_relative_path}
              如果无需迁移（目录不存在/幂等检测通过）返回空 dict

    异常:
        MigrationError: 迁移失败且回滚完成时抛出（调用方应返回错误给前端）
        MigrationRollbackError: 迁移失败且回滚也失败时抛出（需人工介入）
    """
    start_time = time.time()
    student_id = student.get('id')

    # 预计算路径信息（用于审计日志）
    old_dir_name = _compute_dir_name(
        old_fields['training_type'], old_fields['company'], old_fields['name']
    )
    new_dir_name = _compute_dir_name(
        new_fields['training_type'], new_fields['company'], new_fields['name']
    )
    old_dir_path = f"students/{old_dir_name}/"
    new_dir_path = f"students/{new_dir_name}/"
    changed_fields = _compute_changed_fields(old_fields, new_fields)

    # 1. 计算迁移映射
    path_mapping = _compute_path_mapping(student, old_fields, new_fields)

    # 2. 如果映射为空（目录不存在/无文件），直接返回空 dict
    if not path_mapping:
        logger.info('迁移映射为空（目录不存在或无文件需迁移），跳过迁移')
        return {}

    # 3. 幂等性检测
    if _check_idempotent(path_mapping, student):
        logger.info('幂等性检测通过，无需重复迁移')
        return {}

    # 4. 执行迁移（失败时内部会回滚并抛出 MigrationError）
    try:
        _execute_migration(path_mapping)
    except MigrationError as e:
        # 迁移失败且已回滚 - 记录失败审计日志
        elapsed_ms = int((time.time() - start_time) * 1000)
        rollback_files = [old_key for old_key, _ in path_mapping]
        fail_message = f"文件迁移失败: {e}，已回滚 {len(rollback_files)} 个文件"

        try:
            create_operation_log(
                student_id=student_id,
                action='student_files_migrated',
                action_label='学员文件迁移',
                status='fail',
                message=fail_message,
                before=json.loads(json.dumps(
                    {'dir': old_dir_path, 'fields': old_fields},
                    ensure_ascii=False,
                )),
                after=json.loads(json.dumps(
                    {'dir': new_dir_path, 'fields': new_fields},
                    ensure_ascii=False,
                )),
                metadata={
                    'file_count': len(path_mapping),
                    'elapsed_ms': elapsed_ms,
                    'changed_fields': changed_fields,
                    'rollback_files': rollback_files,
                },
            )
        except Exception as log_err:
            logger.warning(f'记录迁移失败审计日志时出错: {log_err}')

        raise

    # 5. 清理旧主目录（如果为空则删除）
    old_main_dir = os.path.join(get_base_dir(), 'students', old_dir_name)
    if os.path.isdir(old_main_dir):
        try:
            # os.rmdir 只能删除空目录，如果目录非空会抛出 OSError
            os.rmdir(old_main_dir)
            logger.info(f'已删除旧空目录: {old_main_dir}')
        except OSError:
            # 目录非空（可能有其他学员的文件），不删除
            logger.debug(f'旧目录非空，保留: {old_main_dir}')

    # 6. 构建返回的 DB 路径更新字典
    #    只包含 _PATH_FIELDS 中有对应映射的字段
    old_to_new = {old_key: new_key for old_key, new_key in path_mapping}
    db_updates = {}
    for field in _PATH_FIELDS:
        old_path = student.get(field, '') or ''
        if old_path and old_path in old_to_new:
            db_updates[field] = old_to_new[old_path]

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f'文件迁移完成: {len(path_mapping)} 个文件, '
        f'耗时 {elapsed_ms}ms, '
        f'DB 字段更新 {len(db_updates)} 个'
    )

    # 7. 记录成功审计日志
    success_message = (
        f"迁移完成: {len(path_mapping)} 个文件从 {old_dir_path} 迁移到 {new_dir_path}，"
        f"耗时 {elapsed_ms}ms"
    )

    # 学员状态为 registered 时追加警告
    if student.get('status') == 'registered':
        success_message += "；警告：学员已报名省网，本次本地改名不会同步到省网，请自行处理省网数据一致性"

    try:
        create_operation_log(
            student_id=student_id,
            action='student_files_migrated',
            action_label='学员文件迁移',
            status='success',
            message=success_message,
            before=json.loads(json.dumps(
                {'dir': old_dir_path, 'fields': old_fields},
                ensure_ascii=False,
            )),
            after=json.loads(json.dumps(
                {'dir': new_dir_path, 'fields': new_fields},
                ensure_ascii=False,
            )),
            metadata={
                'file_count': len(path_mapping),
                'elapsed_ms': elapsed_ms,
                'changed_fields': changed_fields,
            },
        )
    except Exception as log_err:
        logger.warning(f'记录迁移成功审计日志时出错: {log_err}')

    return db_updates
