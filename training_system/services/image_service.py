"""Image processing service."""
import os
import io
from PIL import Image, ImageOps
import numpy as np
from flask import current_app

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from rembg import remove, new_session
except ImportError:
    remove = None
    new_session = None


def change_id_photo_bg(input_path, output_path, bg_color=(255, 255, 255)):
    """
    Replace ID photo background with specified color (default white).

    Args:
        input_path: Input photo path
        output_path: Output photo path
        bg_color: Background color tuple (R, G, B)

    Returns:
        str: Path to processed photo (output_path on success, input_path on failure)
    """
    if remove is None or new_session is None or cv2 is None:
        current_app.logger.warning('rembg or cv2 not available, skipping background removal')
        return input_path

    try:
        # Configure rembg session with alpha matting for better edge detection
        session = new_session(
            model_name="u2net_human_seg",
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_size=10
        )

        # Read and remove background
        with open(input_path, "rb") as f:
            input_img = f.read()
        output_img = remove(input_img, session=session)
        img_no_bg = Image.open(io.BytesIO(output_img)).convert("RGBA")

        # Fix mask to avoid missing clothing areas
        img_np = np.array(img_no_bg)
        alpha_channel = img_np[:, :, 3]
        kernel = np.ones((3, 3), np.uint8)
        alpha_channel = cv2.dilate(alpha_channel, kernel, iterations=1)
        img_np[:, :, 3] = alpha_channel
        img_no_bg_fixed = Image.fromarray(img_np, mode="RGBA")

        # Create white background and composite
        bg_img = Image.new("RGBA", img_no_bg_fixed.size, bg_color + (255,))
        result = Image.alpha_composite(bg_img, img_no_bg_fixed)
        result = result.convert("RGB")

        # Save processed image
        result.save(output_path, quality=95)
        current_app.logger.info(f'Background replaced successfully: {output_path}')
        return output_path
    except Exception as e:
        current_app.logger.error(f'Background replacement failed: {str(e)}')
        return input_path


def process_and_save_file(file_storage, id_card, name, label_key, company=''):
    """
    Save uploaded file with naming pattern '<company>-<name>/<id_card><name>-<label>.<ext>'.

    Args:
        file_storage: FileStorage object from request.files
        id_card: Student ID card number
        name: Student name
        label_key: File label key (e.g., 'photo', 'diploma')
        company: Company name

    Returns:
        str: Relative path like 'students/<company>-<name>/...'
    """
    if not file_storage or not file_storage.filename:
        return ''

    # Label name mapping
    label_name_map = {
        'photo': '个人照片',
        'diploma': '学历证书',
        'cert_front': '所持证件正面',
        'cert_back': '所持证件反面',
        'id_card_front': '身份证正面',
        'id_card_back': '身份证反面'
    }

    label_name = label_name_map.get(label_key, label_key)
    _, ext = os.path.splitext(file_storage.filename)
    orig_ext = ext.lower() if ext else '.jpg'

    # Create student folder
    student_folder_name = f"{company}-{name}"
    student_folder_path = os.path.join(
        current_app.config['STUDENTS_FOLDER'],
        student_folder_name
    )
    os.makedirs(student_folder_path, exist_ok=True)

    # Generate filename
    safe_name = f"{id_card}{name}-{label_name}{orig_ext}"
    abs_path = os.path.join(student_folder_path, safe_name)

    # Save file
    try:
        file_storage.save(abs_path)
        current_app.logger.info(f'File saved: {abs_path}')
    except Exception as e:
        current_app.logger.error(f'Failed to save file: {str(e)}')
        raise

    return f"students/{student_folder_name}/{safe_name}"


def delete_file_if_exists(file_path, base_dir):
    """
    Delete a file if it exists.

    Args:
        file_path: Relative file path
        base_dir: Base directory

    Returns:
        bool: True if file was deleted, False otherwise
    """
    if not file_path:
        return False

    try:
        # Handle both old and new path formats
        if file_path.startswith('students/'):
            abs_path = os.path.join(base_dir, file_path)
        else:
            # Old format: uploads/filename
            filename = os.path.basename(file_path)
            abs_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        if os.path.exists(abs_path):
            os.remove(abs_path)
            current_app.logger.info(f'File deleted: {abs_path}')

            # Try to remove empty student folder
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
    Delete all files associated with a student.

    Args:
        student_record: Student record dictionary
        base_dir: Base directory
    """
    file_keys = [
        'photo_path', 'diploma_path', 'cert_front_path', 'cert_back_path',
        'id_card_front_path', 'id_card_back_path', 'training_form_path'
    ]

    for key in file_keys:
        if student_record.get(key):
            delete_file_if_exists(student_record[key], base_dir)
