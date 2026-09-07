"""
图片处理服务。

本模块提供学员附件文件的处理和管理功能：

核心功能:
    1. 证件照背景替换：使用 rembg 去除原始背景，替换为白色背景
    2. 文件保存：按统一的命名规范和目录结构保存上传的附件文件
    3. 文件清理：删除学员记录时同步清理关联的所有附件文件

文件命名规范:
    目录: students/<培训类型>-<公司>-<姓名>/
    文件: <身份证号>-<姓名>-<附件类型>.<扩展名>
    示例: students/特种设备-阳泉市公司-张三/123456789012345678-张三-个人照片.jpg

存储后端:
    通过 services/storage_service.py 统一管理，支持本地、COS、双写三种模式。
    dual 模式下文件同时保存到本地和 COS，本地用于服务端处理，COS 提供对外访问 URL。

可选依赖:
    - rembg : AI 背景去除库（未安装时背景替换功能自动跳过）
    - cv2   : OpenCV，用于图像掩码修复（未安装时同上）
"""
import os
import io
import logging
from PIL import Image, ImageOps
import numpy as np
from flask import current_app
from services import storage_service

logger = logging.getLogger(__name__)

ATTACHMENT_LABELS = {
    'photo': '个人照片',
    'diploma': '学历证书',
    'id_card_front': '身份证正面',
    'id_card_back': '身份证反面',
    'hukou_residence': '户口本户籍页',
    'hukou_personal': '户口本个人页',
    'certificate_info_page': '原证件说明和个人信息页',
    'certificate_records_page': '原证件作业项目和聘用记录页',
}


def get_attachment_label(label_key):
    return ATTACHMENT_LABELS.get(label_key, label_key)

# ======================== 可选依赖加载 ========================
# rembg 和 cv2 是可选依赖，未安装时背景替换功能自动降级（返回原图）
CV2_IMPORT_ERROR = ''
REMBG_IMPORT_ERROR = ''
REMBG_SESSION_IMPORT_ERROR = ''

try:
    import cv2
except Exception as err:
    cv2 = None
    CV2_IMPORT_ERROR = str(err)

try:
    from rembg import remove
except Exception as err:
    remove = None
    REMBG_IMPORT_ERROR = str(err)

try:
    from rembg import new_session
except Exception as err:
    new_session = None
    REMBG_SESSION_IMPORT_ERROR = str(err)


# ======================== Rembg 单例会话缓存 ========================
_rembg_session = None

def _get_rembg_session():
    """懒加载并返回全局单例的 rembg 会话，避免重复加载 AI 模型造成内存泄露。"""
    global _rembg_session
    if _rembg_session is None and new_session is not None:
        try:
            _rembg_session = new_session(
                model_name="u2net_human_seg",
                alpha_matting=True,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10
            )
        except Exception as err:
            current_app.logger.error(f'初始化 rembg 会话失败: {err}')
    return _rembg_session


def change_id_photo_bg(input_path, output_path, bg_color=(255, 255, 255)):
    """
    将证件照背景替换为指定颜色（默认白色）。

    参数:
        input_path: 输入照片本地路径
        output_path: 输出照片本地路径
        bg_color: 背景颜色元组 (R, G, B)

    返回:
        str: 处理后的照片路径（成功返回 output_path，失败返回 input_path）
    """
    # 检查必要的依赖库是否可用
    if remove is None or cv2 is None:
        current_app.logger.warning(
            'rembg/cv2 unavailable, skipping background removal; cv2_error=%s rembg_error=%s',
            CV2_IMPORT_ERROR or '-',
            REMBG_IMPORT_ERROR or '-'
        )
        # 依赖库不可用时直接返回原始图片路径
        return input_path

    try:
        # 读取并移除背景
        with open(input_path, "rb") as f:
            input_img = f.read()

        # 使用复用的单例会话去除背景，避免重复加载神经网络参数
        session = _get_rembg_session()
        if session is not None:
            output_img = remove(input_img, session=session)
        else:
            # new_session 不可用时回退到默认会话
            if REMBG_SESSION_IMPORT_ERROR:
                current_app.logger.warning(
                    'rembg.new_session unavailable, using default session; detail=%s',
                    REMBG_SESSION_IMPORT_ERROR
                )
            output_img = remove(input_img)
        
        img_no_bg = Image.open(io.BytesIO(output_img)).convert("RGBA")

        # 修复透明度掩码：用形态学膨胀处理 alpha 通道
        # 避免去背景后服装等区域出现透明缝隙
        img_np = np.array(img_no_bg)
        alpha_channel = img_np[:, :, 3]
        kernel = np.ones((3, 3), np.uint8)  # 3x3 节级核
        alpha_channel = cv2.dilate(alpha_channel, kernel, iterations=1)  # 膨胀一次填充缝隙
        img_np[:, :, 3] = alpha_channel
        img_no_bg_fixed = Image.fromarray(img_np, mode="RGBA")

        # 创建指定颜色的背景图层，与去背景的图像进行 alpha 合成
        bg_img = Image.new("RGBA", img_no_bg_fixed.size, bg_color + (255,))
        result = Image.alpha_composite(bg_img, img_no_bg_fixed)
        result = result.convert("RGB")  # 转换为 RGB 模式以保存为 JPEG

        # 保存处理后的图片
        result.save(output_path, quality=95)
        current_app.logger.info(f'图片背景替换成功: {output_path}')
        
        # 显式关闭图片对象，加速内存释放
        try:
            img_no_bg.close()
            img_no_bg_fixed.close()
            bg_img.close()
            result.close()
        except Exception:
            pass

        return output_path
    except Exception as e:
        current_app.logger.error(f'图片背景替换失败: {str(e)}')
        return input_path


def save_temp_file(file_storage, file_type):
    """
    小程序预上传时，将文件暂存到 students/tmp/ 下（扁平结构，无子文件夹）。

    dual/local 模式：保存到本地并同步至 COS（如果配置了 COS）。
    返回临时相对路径，格式：students/tmp/<uuid>_<file_type><ext>

    提交学员表单时，调用 commit_temp_files() 将所有临时文件
    整体移动到正式目录，并返回正式相对路径。

    参数:
        file_storage: werkzeug FileStorage 对象
        file_type: 附件类型（如 'photo', 'diploma'）

    返回:
        str: 临时 key（相对路径），失败返回空字符串
    """
    import uuid
    if not file_storage or not file_storage.filename:
        return ''

    _, ext = os.path.splitext(file_storage.filename)
    orig_ext = ext.lower() if ext else '.jpg'

    tmp_id = str(uuid.uuid4())
    filename = f"{tmp_id}_{file_type}{orig_ext}"
    tmp_key = f"students/tmp/{filename}"

    # 通过存储服务保存（dual 模式同时写本地和 COS）
    storage_service.save_file(file_storage, tmp_key)
    current_app.logger.info(f'临时文件已保存: {tmp_key}')

    return tmp_key


def commit_temp_files(tmp_paths_by_input_name, id_card, name, company, training_type):
    """
    提交阶段：将预上传的临时文件移动到学员正式目录，返回正式的相对路径字典。

    dual 模式下本地和 COS 同步移动（本地 shutil.move + COS 服务端复制删除）。

    参数:
        tmp_paths_by_input_name : {input_name -> tmp relative path}
        id_card, name, company, training_type : 用于生成正式文件夹名
    返回:
        {db_key -> formal relative path}
    """
    training_type_map = {
        'special_operation': '特种作业',
        'special_equipment': '特种设备',
    }
    training_type_name = training_type_map.get(training_type, '特种作业')
    student_folder_name = f"{training_type_name}-{company}-{name}"

    from routes.student_routes import FILE_MAP  # 延迟导入避免循环
    result = {}
    tmp_dirs_to_clean = set()

    for input_name, db_key in FILE_MAP.items():
        tmp_rel = tmp_paths_by_input_name.get(input_name, '')
        if not tmp_rel or not tmp_rel.startswith('students/tmp/'):
            result[db_key] = ''
            continue

        # 检查临时文件是否存在（本地或 COS）
        if not storage_service.file_exists_local(tmp_rel):
            current_app.logger.warning(f'未找到临时文件: {tmp_rel}')
            result[db_key] = ''
            continue

        _, ext = os.path.splitext(tmp_rel)
        label_name = get_attachment_label(input_name)
        safe_name = f"{id_card}-{name}-{label_name}{ext}"
        formal_key = f"students/{student_folder_name}/{safe_name}"

        # 通过存储服务移动（dual 模式本地 + COS 同步移动）
        ok = storage_service.move_temp_file(tmp_rel, formal_key)
        if ok:
            current_app.logger.info(f'正式归档小程序的临时附件文件: {tmp_rel} -> {formal_key}')
            result[db_key] = formal_key
            # 记录临时目录用于后续清理
            tmp_dirs_to_clean.add(os.path.dirname(tmp_rel))
        else:
            current_app.logger.error(f'归档临时文件失败: {tmp_rel}')
            result[db_key] = ''

    return result


def process_and_save_file(file_storage, id_card, name, label_key, company='', training_type='special_operation'):
    """
    保存上传文件，命名格式为 '<培训类型>-<公司>-<姓名>/<身份证号>-<姓名>-<标签>.<扩展名>'。

    dual 模式：先写入本地，再同步至 COS。
    本地文件供服务端处理（材料生成等）使用，COS 文件提供给用户访问。

    参数:
        file_storage: 来自 request.files 的 FileStorage 对象
        id_card: 学员身份证号
        name: 学员姓名
        label_key: 文件标签键（如 'photo', 'diploma'）
        company: 公司名称
        training_type: 培训类型（special_operation 或 special_equipment）

    返回:
        str: 相对路径（存储 key），如 'students/<培训类型>-<公司>-<姓名>/...'

    异常:
        文件保存失败时向上抛出异常
    """
    if not file_storage or not file_storage.filename:
        return ''

    # 前端字段名 -> 中文附件标签映射（用于生成可读的文件名）
    label_name = get_attachment_label(label_key)
    _, ext = os.path.splitext(file_storage.filename)
    orig_ext = ext.lower() if ext else '.jpg'  # 无扩展名时默认为 .jpg

    # 培训类型英文键 -> 中文名称映射（用于文件夹命名）
    training_type_map = {
        'special_operation': '特种作业',
        'special_equipment': '特种设备'
    }
    training_type_name = training_type_map.get(training_type, '特种作业')

    # 生成存储 key（相对路径）
    student_folder_name = f"{training_type_name}-{company}-{name}"
    safe_name = f"{id_card}-{name}-{label_name}{orig_ext}"
    key = f"students/{student_folder_name}/{safe_name}"

    # 通过存储服务保存（dual 模式同时写本地和 COS，原子写保证本地安全）
    storage_service.save_file(file_storage, key)
    current_app.logger.info(f'文件已保存: {key}')

    return key


def delete_file_if_exists(file_path, base_dir):
    """
    如果文件存在则删除（本地 + COS）。

    参数:
        file_path: 相对文件路径（存储 key）
        base_dir: 基础目录（兼容旧接口，实际由 storage_service 内部获取）

    返回:
        bool: 删除成功返回 True，否则返回 False
    """
    if not file_path:
        return False
    return storage_service.delete_file(file_path)


def _is_file_in_use_by_other_students(rel_path, exclude_student_id=None):
    """
    检查指定相对路径的文件是否仍被其他学员记录引用（例如同人报考多工种共用证件照）。
    返回: (in_use: bool, other_student_id: int|None)
    """
    if not rel_path:
        return False, None
    try:
        from models.student import get_db_connection
        file_cols = [
            'photo_path', 'diploma_path',
            'id_card_front_path', 'id_card_back_path',
            'hukou_residence_path', 'hukou_personal_path',
            'certificate_info_page_path', 'certificate_records_page_path',
            'training_form_path'
        ]
        where_or = ' OR '.join([f"{col} = ?" for col in file_cols])
        sql = f"SELECT id FROM students WHERE ({where_or})"
        params = [rel_path] * len(file_cols)
        if exclude_student_id is not None:
            sql += " AND id != ?"
            params.append(exclude_student_id)
        sql += " LIMIT 1"
        with get_db_connection() as conn:
            row = conn.execute(sql, params).fetchone()
            if row:
                return True, row['id']
    except Exception as e:
        logger.debug(f"检查文件引用状态异常（容错跳过）: {e}")
    return False, None


def _is_folder_in_use_by_other_students(folder_prefix, student_record, exclude_student_id=None):
    """
    检查指定学员目录前缀是否仍被其他有效学员记录（同一人报考多个工种、或同一单位同名学员）使用。
    返回: (in_use: bool, other_student_ids: list)
    """
    if not folder_prefix:
        return False, []
    try:
        from models.student import get_db_connection
        file_cols = [
            'photo_path', 'diploma_path',
            'id_card_front_path', 'id_card_back_path',
            'hukou_residence_path', 'hukou_personal_path',
            'certificate_info_page_path', 'certificate_records_page_path',
            'training_form_path'
        ]
        # 条件 1：任意路径字段位于该 folder_prefix 目录下
        prefix_pattern = folder_prefix.rstrip('/') + '/%'
        prefix_exact = folder_prefix.rstrip('/')
        path_clauses = [f"({col} LIKE ? OR {col} = ?)" for col in file_cols]
        path_params = []
        for _ in file_cols:
            path_params.extend([prefix_pattern, prefix_exact])

        # 条件 2：同姓名 + 同公司 + 同培训类别（即使尚未生成材料或路径为空，其归属目录也是此目录）
        name = (student_record.get('name') or '').strip()
        company = (student_record.get('company') or '').strip()
        training_type = (student_record.get('training_type') or '').strip()

        where_branches = [f"({' OR '.join(path_clauses)})"]
        all_params = list(path_params)

        if name and company and training_type:
            where_branches.append("(name = ? AND company = ? AND training_type = ?)")
            all_params.extend([name, company, training_type])

        sql = f"SELECT id FROM students WHERE ({' OR '.join(where_branches)})"
        if exclude_student_id is not None:
            sql += " AND id != ?"
            all_params.append(exclude_student_id)

        with get_db_connection() as conn:
            rows = conn.execute(sql, all_params).fetchall()
            if rows:
                return True, [r['id'] for r in rows]
    except Exception as e:
        logger.debug(f"检查目录前缀引用状态异常（容错跳过）: {e}")
    return False, []


def delete_student_files(student_record, base_dir=None):
    """
    删除学员关联的所有文件（本地 + COS），包括原始单项附件和自动生成的报名材料全量目录。
    具备多引用安全保护：若其他学员记录（如同一学员报了其他工种）仍在使用该文件或目录，严禁物理删除。

    参数:
        student_record: 学员记录字典（含各 *_path 字段及 name, company, training_type 等）
        base_dir: 基础目录（兼容旧接口）

    返回:
        dict: {'success': bool, 'failed_files': list}
    """
    if not isinstance(student_record, dict):
        return {'success': True, 'failed_files': []}

    student_id = student_record.get('id')

    file_keys = [
        'photo_path', 'diploma_path',
        'id_card_front_path', 'id_card_back_path',
        'hukou_residence_path', 'hukou_personal_path',
        'certificate_info_page_path', 'certificate_records_page_path',
        'training_form_path'
    ]

    failed_files = []
    # 1. 逐个删除单项关联文件（受单文件引用保护）
    for key in file_keys:
        rel_path = student_record.get(key)
        if rel_path:
            in_use, other_id = _is_file_in_use_by_other_students(rel_path, exclude_student_id=student_id)
            if in_use:
                logger.info(
                    f"[删除保护] 文件 {rel_path} 仍被其他学员记录(ID={other_id})引用，跳过物理删除"
                )
                continue
            ok = storage_service.delete_file(rel_path)
            if not ok:
                failed_files.append(rel_path)

    # 2. 计算学员主目录前缀并彻底清理（受整目录引用保护）
    try:
        from services import student_folder_service
        folder_prefix = student_folder_service.get_student_folder_prefix(student_record)
        if folder_prefix:
            folder_in_use, other_ids = _is_folder_in_use_by_other_students(
                folder_prefix, student_record, exclude_student_id=student_id
            )
            if folder_in_use:
                logger.warning(
                    f"[删除保护] 目录 {folder_prefix} 仍有其他有效学员记录在用 (共用学员ID: {other_ids})，"
                    f"跳过整目录清空，保护多项目学员附件！"
                )
            else:
                prefix_res = storage_service.delete_prefix(folder_prefix)
                if not prefix_res.get('success'):
                    failed_files.extend(prefix_res.get('failed_keys', []))
    except Exception as e:
        logger.error(f"清理学员前缀目录失败: {e}", exc_info=True)
        failed_files.append(f"folder_prefix_error:{e}")

    success = len(failed_files) == 0
    if not success:
        logger.warning(f"学员文件/目录清理存在未成功项 (ID={student_record.get('id')}): {failed_files}")
    else:
        logger.info(f"学员文件及生成材料目录清理处理完毕 (ID={student_record.get('id')})")

    return {'success': success, 'failed_files': failed_files}

