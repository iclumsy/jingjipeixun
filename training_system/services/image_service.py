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
from PIL import Image, ImageOps
import numpy as np
from flask import current_app
from services import storage_service

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

        # 使用 rembg 去除背景
        # 优先使用 u2net_human_seg 模型（专为人像优化）
        # alpha_matting 参数控制边缘精度，避免强硬的剪裁边缘
        if new_session is not None:
            session = new_session(
                model_name="u2net_human_seg",
                alpha_matting=True,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10
            )
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
        current_app.logger.info(f'Background replaced successfully: {output_path}')
        return output_path
    except Exception as e:
        current_app.logger.error(f'Background replacement failed: {str(e)}')
        return input_path


def save_temp_file(file_storage, file_type):
    """
    小程序预上传时，将文件暂存到 students/tmp/<uuid>/ 下。

    dual/local 模式：保存到本地并同步至 COS（如果配置了 COS）。
    返回临时相对路径，格式：students/tmp/<uuid>/<file_type><ext>

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
    filename = f"{file_type}{orig_ext}"
    tmp_key = f"students/tmp/{tmp_id}/{filename}"

    # 通过存储服务保存（dual 模式同时写本地和 COS）
    storage_service.save_file(file_storage, tmp_key)
    current_app.logger.info(f'Temp file saved: {tmp_key}')

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
    label_name_map = {
        'photo': '个人照片',
        'diploma': '学历证书',
        'id_card_front': '身份证正面',
        'id_card_back': '身份证反面',
        'hukou_residence': '户口本户籍页',
        'hukou_personal': '户口本个人页',
    }
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
            current_app.logger.warning(f'Temp file not found: {tmp_rel}')
            result[db_key] = ''
            continue

        _, ext = os.path.splitext(tmp_rel)
        label_name = label_name_map.get(input_name, input_name)
        safe_name = f"{id_card}-{name}-{label_name}{ext}"
        formal_key = f"students/{student_folder_name}/{safe_name}"

        # 通过存储服务移动（dual 模式本地 + COS 同步移动）
        ok = storage_service.move_temp_file(tmp_rel, formal_key)
        if ok:
            current_app.logger.info(f'Committed temp file: {tmp_rel} -> {formal_key}')
            result[db_key] = formal_key
            # 记录临时目录用于后续清理
            tmp_dirs_to_clean.add(os.path.dirname(tmp_rel))
        else:
            current_app.logger.error(f'Failed to commit temp file {tmp_rel}')
            result[db_key] = ''

    # 清理已搬空的本地临时文件夹
    base_dir = current_app.config['BASE_DIR']
    for tmp_rel_dir in tmp_dirs_to_clean:
        tmp_abs_dir = os.path.join(base_dir, tmp_rel_dir)
        try:
            if os.path.isdir(tmp_abs_dir) and not os.listdir(tmp_abs_dir):
                os.rmdir(tmp_abs_dir)
        except Exception:
            pass

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
    label_name_map = {
        'photo': '个人照片',
        'diploma': '学历证书',
        'id_card_front': '身份证正面',
        'id_card_back': '身份证反面',
        'hukou_residence': '户口本户籍页',
        'hukou_personal': '户口本个人页'
    }

    label_name = label_name_map.get(label_key, label_key)
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
    current_app.logger.info(f'File saved: {key}')

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


def delete_student_files(student_record, base_dir):
    """
    删除学员关联的所有文件（本地 + COS）。

    参数:
        student_record: 学员记录字典（含各 *_path 字段）
        base_dir: 基础目录（兼容旧接口，实际由 storage_service 内部获取）
    """
    # 所有可能含有文件路径的数据库字段
    file_keys = [
        'photo_path', 'diploma_path',
        'id_card_front_path', 'id_card_back_path',
        'hukou_residence_path', 'hukou_personal_path', 'training_form_path'
    ]

    # 逐个删除关联文件
    for key in file_keys:
        if student_record.get(key):
            storage_service.delete_file(student_record[key])
