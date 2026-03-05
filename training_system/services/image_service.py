"""图片处理服务。"""
import os
import io
from PIL import Image, ImageOps
import numpy as np
from flask import current_app

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
        input_path: 输入照片路径
        output_path: 输出照片路径
        bg_color: 背景颜色元组 (R, G, B)

    返回:
        str: 处理后的照片路径（成功返回 output_path，失败返回 input_path）
    """
    if remove is None or cv2 is None:
        current_app.logger.warning(
            'rembg/cv2 unavailable, skipping background removal; cv2_error=%s rembg_error=%s',
            CV2_IMPORT_ERROR or '-',
            REMBG_IMPORT_ERROR or '-'
        )
        return input_path

    try:
        # 读取并移除背景
        with open(input_path, "rb") as f:
            input_img = f.read()

        # 优先使用显式会话；否则回退到默认 remove()
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
            if REMBG_SESSION_IMPORT_ERROR:
                current_app.logger.warning(
                    'rembg.new_session unavailable, using default session; detail=%s',
                    REMBG_SESSION_IMPORT_ERROR
                )
            output_img = remove(input_img)
        img_no_bg = Image.open(io.BytesIO(output_img)).convert("RGBA")

        # 修复掩码，避免服装区域缺失
        img_np = np.array(img_no_bg)
        alpha_channel = img_np[:, :, 3]
        kernel = np.ones((3, 3), np.uint8)
        alpha_channel = cv2.dilate(alpha_channel, kernel, iterations=1)
        img_np[:, :, 3] = alpha_channel
        img_no_bg_fixed = Image.fromarray(img_np, mode="RGBA")

        # 创建白色背景并合成
        bg_img = Image.new("RGBA", img_no_bg_fixed.size, bg_color + (255,))
        result = Image.alpha_composite(bg_img, img_no_bg_fixed)
        result = result.convert("RGB")

        # 保存处理后的图片
        result.save(output_path, quality=95)
        current_app.logger.info(f'Background replaced successfully: {output_path}')
        return output_path
    except Exception as e:
        current_app.logger.error(f'Background replacement failed: {str(e)}')
        return input_path


def process_and_save_file(file_storage, id_card, name, label_key, company='', training_type='special_operation'):
    """
    保存上传文件，命名格式为 '<公司>-<姓名>/<身份证号><姓名>-<标签>.<扩展名>'。

    参数:
        file_storage: 来自 request.files 的 FileStorage 对象
        id_card: 学员身份证号
        name: 学员姓名
        label_key: 文件标签键（如 'photo', 'diploma'）
        company: 公司名称
        training_type: 培训类型（special_operation 或 special_equipment）

    返回:
        str: 相对路径，如 'students/<培训类型>-<公司>-<姓名>/...'
    """
    if not file_storage or not file_storage.filename:
        return ''

    # 标签名称映射
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
    orig_ext = ext.lower() if ext else '.jpg'

    # 培训类型映射为中文名称
    training_type_map = {
        'special_operation': '特种作业',
        'special_equipment': '特种设备'
    }
    training_type_name = training_type_map.get(training_type, '特种作业')

    # 创建学员文件夹
    student_folder_name = f"{training_type_name}-{company}-{name}"
    student_folder_path = os.path.join(
        current_app.config['STUDENTS_FOLDER'],
        student_folder_name
    )
    os.makedirs(student_folder_path, exist_ok=True)

    # 生成文件名
    safe_name = f"{id_card}-{name}-{label_name}{orig_ext}"
    abs_path = os.path.join(student_folder_path, safe_name)

    # 保存文件
    try:
        file_storage.save(abs_path)
        current_app.logger.info(f'File saved: {abs_path}')
    except Exception as e:
        current_app.logger.error(f'Failed to save file: {str(e)}')
        raise

    return f"students/{student_folder_name}/{safe_name}"


def delete_file_if_exists(file_path, base_dir):
    """
    如果文件存在则删除。

    参数:
        file_path: 相对文件路径
        base_dir: 基础目录

    返回:
        bool: 删除成功返回 True，否则返回 False
    """
    if not file_path:
        return False

    try:
        abs_path = os.path.join(base_dir, file_path)

        if os.path.exists(abs_path):
            os.remove(abs_path)
            current_app.logger.info(f'File deleted: {abs_path}')

            # 尝试删除空的学员文件夹
            if file_path.startswith('students/'):
                folder_path = os.path.dirname(abs_path)
                if os.path.isdir(folder_path) and not os.listdir(folder_path):
                    os.rmdir(folder_path)
                    current_app.logger.info(f'Empty folder removed: {folder_path}')

            return True
    except Exception as e:
        current_app.logger.error(f'Failed to delete file {file_path}: {str(e)}')

    return False


def delete_student_files(student_record, base_dir):
    """
    删除学员关联的所有文件。

    参数:
        student_record: 学员记录字典
        base_dir: 基础目录
    """
    file_keys = [
        'photo_path', 'diploma_path',
        'id_card_front_path', 'id_card_back_path',
        'hukou_residence_path', 'hukou_personal_path', 'training_form_path'
    ]

    for key in file_keys:
        if student_record.get(key):
            delete_file_if_exists(student_record[key], base_dir)
