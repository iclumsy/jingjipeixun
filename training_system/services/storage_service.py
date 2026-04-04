"""
统一文件存储服务（双写模式）。

支持三种存储后端，通过环境变量 STORAGE_BACKEND 控制：
  - local（默认）: 仅使用本地文件系统（纯本地开发）
  - cos           : 仅使用腾讯云 COS（无本地备份）
  - dual（推荐）  : 本地 + COS 双写，本地保留备份供服务端处理，
                    COS 提供给用户访问（公读桶，永久有效 URL）

双写模式（dual）行为：
  - 上传：先写本地，再异步推 COS（本地写失败则整体失败）
  - 服务端读取（生成材料等）：直接读本地文件，无需走网络
  - 对外 URL：返回 COS 公网 URL
  - 删除：本地 + COS 同时删除
  - 文件列举：基于本地文件系统（速度快）

数据库中存储的相对路径（如 students/特种设备-XX公司-张三/xxx.jpg）
在所有后端中含义一致，local 后端拼接 BASE_DIR 得到绝对路径，
COS 后端直接作为 object key 使用。

公读私写桶配置说明：
  COS 桶设置为公读私写后，文件公网 URL 格式为：
  https://<bucket>-<appid>.cos.<region>.myqcloud.com/<key>
  无需预签名，永久有效，直接返回给前端使用。
"""
import os
import io


# ======================== 后端选择 ========================

def _get_backend():
    """读取 STORAGE_BACKEND 环境变量，返回 'local'、'cos' 或 'dual'。"""
    return os.getenv('STORAGE_BACKEND', 'local').strip().lower()


# ======================== COS 客户端单例 ========================

_cos_client = None
_cos_config = None


def _get_cos_client():
    """
    懒加载方式初始化并返回 COS 客户端单例。

    返回:
        tuple: (CosS3Client, config_dict)

    异常:
        RuntimeError: COS 配置不完整时抛出
    """
    global _cos_client, _cos_config
    if _cos_client is not None:
        return _cos_client, _cos_config

    from qcloud_cos import CosConfig, CosS3Client

    secret_id  = os.getenv('COS_SECRET_ID', '')
    secret_key = os.getenv('COS_SECRET_KEY', '')
    region     = os.getenv('COS_REGION', '')
    bucket     = os.getenv('COS_BUCKET', '')

    if not all([secret_id, secret_key, region, bucket]):
        raise RuntimeError(
            'COS 配置不完整，请在 .env 中设置 '
            'COS_SECRET_ID / COS_SECRET_KEY / COS_REGION / COS_BUCKET'
        )

    config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
    _cos_client = CosS3Client(config)
    _cos_config = {
        'bucket': bucket,
        'region': region,
        'prefix': os.getenv('COS_KEY_PREFIX', '').strip().rstrip('/'),
    }
    return _cos_client, _cos_config


def _full_cos_key(key, config):
    """
    如果配置了 COS_KEY_PREFIX，拼接前缀生成完整 COS key。

    参数:
        key: 相对路径，如 'students/xxx/yyy.jpg'
        config: COS 配置字典

    返回:
        str: 完整 COS key
    """
    prefix = config.get('prefix', '')
    if prefix:
        return f"{prefix}/{key}"
    return key


def _push_to_cos(data_bytes, key):
    """
    将字节数据上传到 COS。内部函数，上层调用出错时由调用方决定是否中断。

    参数:
        data_bytes: bytes 对象
        key: 存储 key（相对路径）
    """
    client, config = _get_cos_client()
    full = _full_cos_key(key, config)
    client.put_object(
        Bucket=config['bucket'],
        Body=data_bytes,
        Key=full,
    )
    _log_info(f'COS upload: key={key}')


# ======================== 基础目录 ========================

def get_base_dir():
    """
    获取本地存储基础目录。

    在 Flask 请求上下文中从 current_app.config 获取；
    在脚本/测试上下文中回退到 app.py 所在目录的父目录。
    """
    try:
        from flask import current_app
        return current_app.config['BASE_DIR']
    except RuntimeError:
        # 本文件在 services/ 目录，上一级为项目根目录
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ======================== 写入接口 ========================

def save_file(data_or_fileobj, key):
    """
    保存文件到存储后端。

    - local : 仅写本地
    - cos   : 仅写 COS
    - dual  : 先写本地，再同步至 COS（本地写失败则整体失败）

    参数:
        data_or_fileobj: bytes、BytesIO 或 werkzeug FileStorage 对象
        key: 存储 key，如 'students/xxx/photo.jpg'

    返回:
        str: 存储 key（与传入 key 相同）

    异常:
        写入失败时向上抛出异常
    """
    backend = _get_backend()

    # 标准化为 bytes（一次 read，避免 FileStorage 被消耗后无法重复读取）
    if hasattr(data_or_fileobj, 'read'):
        data = data_or_fileobj.read()
        # 尝试重置，方便调用方后续再次读取（如审计日志）
        if hasattr(data_or_fileobj, 'seek'):
            try:
                data_or_fileobj.seek(0)
            except Exception:
                pass
    else:
        data = bytes(data_or_fileobj)

    if backend in ('local', 'dual'):
        # 写本地文件（原子写：先写 .tmp 再 rename）
        abs_path = os.path.join(get_base_dir(), key)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        tmp_path = abs_path + '.tmp_upload'
        try:
            with open(tmp_path, 'wb') as f:
                f.write(data)
            os.replace(tmp_path, abs_path)
            _log_info(f'Local save: {abs_path}')
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise

    if backend in ('cos', 'dual'):
        # 上传 COS（dual 模式下本地已成功才执行此步骤）
        try:
            _push_to_cos(data, key)
        except Exception as e:
            # dual 模式下 COS 推送失败记警告但不影响业务（本地已有备份）
            if backend == 'dual':
                _log_warning(f'COS sync failed for key={key} (local saved): {e}')
            else:
                raise

    return key


def save_from_local(local_abs_path, key):
    """
    将已存在于本地的文件同步至 COS（dual/cos 模式）。

    用于：material_service、document_service 生成文件后调用，
    这些场景文件已由业务代码写到本地，只需补一步 COS 同步。

    local 模式下此函数为 no-op（文件本就在本地）。

    参数:
        local_abs_path: 本地文件绝对路径
        key: 目标 COS key（通常与本地相对路径一致）

    返回:
        str: key
    """
    backend = _get_backend()

    if backend in ('cos', 'dual'):
        try:
            with open(local_abs_path, 'rb') as f:
                data = f.read()
            _push_to_cos(data, key)
        except Exception as e:
            if backend == 'dual':
                _log_warning(f'COS sync failed for local={local_abs_path}: {e}')
            else:
                raise

    return key


def move_temp_file(src_key, dst_key):
    """
    将临时文件从 src_key 移动到 dst_key（提交阶段调用）。

    - local/dual : 本地使用 shutil.move，dual 模式额外在 COS 执行复制+删除
    - cos        : 仅 COS 服务端复制+删除

    dual 模式 COS 操作失败时记警告不中断（本地已移动成功）。

    参数:
        src_key: 源 key（如 'students/tmp/<uuid>/photo.jpg'）
        dst_key: 目标 key（如 'students/特种设备-XX公司-张三/xxx-photo.jpg'）

    返回:
        bool: 成功返回 True
    """
    if not src_key or not dst_key:
        return False

    backend = _get_backend()

    if backend in ('local', 'dual'):
        import shutil
        base_dir = get_base_dir()
        src_abs = os.path.join(base_dir, src_key)
        dst_abs = os.path.join(base_dir, dst_key)
        if not os.path.exists(src_abs):
            _log_warning(f'move_temp_file: src not found {src_abs}')
            return False
        os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
        shutil.move(src_abs, dst_abs)
        _log_info(f'Local move: {src_key} -> {dst_key}')

        if backend == 'dual':
            # dual 模式：在 COS 端也做移动（复制+删除）
            try:
                client, config = _get_cos_client()
                bucket = config['bucket']
                src_full = _full_cos_key(src_key, config)
                dst_full = _full_cos_key(dst_key, config)
                client.copy_object(
                    Bucket=bucket,
                    Key=dst_full,
                    CopySource={'Bucket': bucket, 'Key': src_full, 'Region': config['region']}
                )
                client.delete_object(Bucket=bucket, Key=src_full)
                _log_info(f'COS move: {src_key} -> {dst_key}')
            except Exception as e:
                # 本地已移动成功，COS 操作失败仅记警告
                # 后续可通过 sync_to_cos 补偿
                _log_warning(f'COS move failed {src_key}->{dst_key}: {e}')

        return True

    else:
        # cos-only 模式
        try:
            client, config = _get_cos_client()
            bucket = config['bucket']
            src_full = _full_cos_key(src_key, config)
            dst_full = _full_cos_key(dst_key, config)
            client.copy_object(
                Bucket=bucket,
                Key=dst_full,
                CopySource={'Bucket': bucket, 'Key': src_full, 'Region': config['region']}
            )
            client.delete_object(Bucket=bucket, Key=src_full)
            return True
        except Exception as e:
            _log_warning(f'COS move failed {src_key}->{dst_key}: {e}')
            return False


def delete_file(key):
    """
    删除存储后端中的文件。

    dual/local: 删本地文件，同时尝试清理空文件夹
    dual/cos  : 同时删 COS 对象
    COS 删除失败不影响本地删除结果（记警告）。

    参数:
        key: 存储 key

    返回:
        bool: 成功（含文件不存在）返回 True，本地删除出错返回 False
    """
    if not key:
        return False

    backend = _get_backend()

    local_ok = True
    if backend in ('local', 'dual'):
        abs_path = os.path.join(get_base_dir(), key)
        try:
            if os.path.exists(abs_path):
                os.remove(abs_path)
                _log_info(f'Local delete: {abs_path}')
                # 清理空文件夹
                if key.startswith('students/'):
                    folder = os.path.dirname(abs_path)
                    if os.path.isdir(folder) and not os.listdir(folder):
                        os.rmdir(folder)
        except Exception as e:
            _log_warning(f'Local delete failed {abs_path}: {e}')
            local_ok = False

    if backend in ('cos', 'dual'):
        try:
            client, config = _get_cos_client()
            full = _full_cos_key(key, config)
            client.delete_object(Bucket=config['bucket'], Key=full)
            _log_info(f'COS delete: {key}')
        except Exception as e:
            _log_warning(f'COS delete failed key={key}: {e}')
            # COS 删除失败不中断，返回本地删除结果

    return local_ok


# ======================== 读取接口 ========================

def read_local(key):
    """
    从本地读取文件内容（bytes）。dual/local 模式专用，速度快。

    参数:
        key: 存储 key

    返回:
        bytes 或 None（文件不存在）
    """
    abs_path = os.path.join(get_base_dir(), key)
    if not os.path.exists(abs_path):
        return None
    with open(abs_path, 'rb') as f:
        return f.read()


def read_bytes(key):
    """
    从存储后端读取文件内容（bytes）。

    dual/local 模式优先读本地；cos-only 模式从 COS 下载。

    参数:
        key: 存储 key

    返回:
        bytes 或 None（文件不存在）
    """
    backend = _get_backend()

    if backend in ('local', 'dual'):
        return read_local(key)

    # cos-only
    try:
        client, config = _get_cos_client()
        full = _full_cos_key(key, config)
        resp = client.get_object(Bucket=config['bucket'], Key=full)
        return resp['Body'].get_raw_stream().read()
    except Exception as e:
        if 'NoSuchKey' in str(e) or '404' in str(e):
            return None
        raise


def local_abs_path(key):
    """
    返回 key 对应的本地绝对路径（不检查是否存在）。

    用于需要传入文件路径的第三方库（如 cv2.imread、docx 模板读取等）。

    参数:
        key: 存储 key

    返回:
        str: 绝对路径
    """
    return os.path.join(get_base_dir(), key)


def file_exists_local(key):
    """检查文件是否存在于本地（dual/local 模式）。"""
    return os.path.exists(os.path.join(get_base_dir(), key))


# ======================== URL 生成 ========================

def get_url(key):
    """
    获取文件的访问 URL。

    - cos/dual 且 COS 已配置：返回 COS 公网 URL（公读桶，永久有效）
    - cos/dual 但 COS 尚未配置：降级为本地 URL，避免循环跳转
    - local：返回 Flask 路由 URL（/key）

    注意：直接读环境变量拼 URL，不刚建 SDK 客户端，
    避免配置不完整时异常降级为本地 URL 再被 serve_students 重定向，
    造成循环跳转。

    参数:
        key: 存储 key，如 'students/xxx/photo.jpg'

    返回:
        str: 资源访问 URL
    """
    backend = _get_backend()

    if backend in ('cos', 'dual'):
        # 直接读环境变量，不需要初始化 SDK
        bucket = os.getenv('COS_BUCKET', '').strip()
        region = os.getenv('COS_REGION', '').strip()
        if bucket and region:
            prefix = os.getenv('COS_KEY_PREFIX', '').strip().rstrip('/')
            full = f"{prefix}/{key}" if prefix else key
            return f"https://{bucket}.cos.{region}.myqcloud.com/{full}"
        # COS 配置不完整，降级本地 URL
        _log_warning(
            'COS_BUCKET 或 COS_REGION 未配置，当前降级为本地 URL'
        )

    return f"/{key}"


# ======================== 文件列举 ========================

def list_dir(prefix, recursive=False):
    """
    列举指定前缀（目录）下的子项。

    dual/local 模式：直接用本地 os.scandir（快速）
    cos-only 模式：调用 COS list_objects

    参数:
        prefix: 目录前缀，如 'students/' 或 'students/xxx/'
        recursive: True 时递归列举所有子文件，False 时仅列举一级

    返回:
        dict: {
            'dirs' : [{'name': '子目录名/', 'prefix': '完整前缀/'}, ...],
            'files': [{'name': '文件名', 'key': '完整key', 'size': int,
                       'last_modified': str}, ...]
        }
    """
    backend = _get_backend()

    if backend in ('local', 'dual'):
        return _list_dir_local(prefix, recursive)
    else:
        return _list_dir_cos(prefix, recursive)


def _list_dir_local(prefix, recursive=False):
    """本地文件系统列举实现。"""
    base_dir = get_base_dir()
    target_dir = os.path.join(base_dir, prefix.rstrip('/'))
    result = {'dirs': [], 'files': []}

    if not os.path.isdir(target_dir):
        return result

    if recursive:
        for root, dirs, filenames in os.walk(target_dir):
            dirs.sort()
            for fn in sorted(filenames):
                abs_path = os.path.join(root, fn)
                stat = os.stat(abs_path)
                rel_key = os.path.relpath(abs_path, base_dir).replace('\\', '/')
                result['files'].append({
                    'name': fn,
                    'key': rel_key,
                    'size': stat.st_size,
                    'last_modified': str(stat.st_mtime),
                })
    else:
        for entry in sorted(os.scandir(target_dir), key=lambda e: e.name):
            if entry.is_dir(follow_symlinks=False):
                result['dirs'].append({
                    'name': entry.name + '/',
                    'prefix': prefix.rstrip('/') + '/' + entry.name + '/',
                })
            elif entry.is_file(follow_symlinks=False):
                stat = entry.stat(follow_symlinks=False)
                rel_key = prefix.rstrip('/') + '/' + entry.name
                result['files'].append({
                    'name': entry.name,
                    'key': rel_key,
                    'size': stat.st_size,
                    'last_modified': str(stat.st_mtime),
                })

    return result


def _list_dir_cos(prefix, recursive=False):
    """COS 列举实现。"""
    client, config = _get_cos_client()
    bucket = config['bucket']
    global_prefix = config.get('prefix', '')
    cos_prefix = _full_cos_key(prefix, config) if prefix else ''
    delimiter = '' if recursive else '/'

    result = {'dirs': [], 'files': []}
    marker = ''

    while True:
        kwargs = {
            'Bucket': bucket,
            'Prefix': cos_prefix,
            'Marker': marker,
            'MaxKeys': 1000,
        }
        if delimiter:
            kwargs['Delimiter'] = delimiter

        resp = client.list_objects(**kwargs)

        for cp in resp.get('CommonPrefixes', []) or []:
            cos_key = cp.get('Prefix', '')
            rel_key = cos_key[len(global_prefix):].lstrip('/') if global_prefix else cos_key
            name = rel_key[len(prefix):] if rel_key.startswith(prefix) else rel_key
            result['dirs'].append({'name': name, 'prefix': rel_key})

        for obj in resp.get('Contents', []) or []:
            cos_key = obj.get('Key', '')
            rel_key = cos_key[len(global_prefix):].lstrip('/') if global_prefix else cos_key
            if rel_key.rstrip('/') == prefix.rstrip('/'):
                continue
            name = os.path.basename(rel_key)
            result['files'].append({
                'name': name,
                'key': rel_key,
                'size': int(obj.get('Size', 0)),
                'last_modified': obj.get('LastModified', ''),
            })

        if resp.get('IsTruncated') == 'true':
            marker = resp.get('NextMarker', '')
        else:
            break

    return result


# ======================== 内部日志 ========================

def _log_warning(msg):
    """安全地写 Flask 日志，若在请求上下文外则降级为 print。"""
    try:
        from flask import current_app
        current_app.logger.warning(msg)
    except RuntimeError:
        print(f'[storage_service WARNING] {msg}')


def _log_info(msg):
    """安全地写 Flask 日志，若在请求上下文外则降级为 print。"""
    try:
        from flask import current_app
        current_app.logger.info(msg)
    except RuntimeError:
        print(f'[storage_service INFO] {msg}')
