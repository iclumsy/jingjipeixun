"""Data validation utilities."""
import re
from utils.error_handlers import ValidationError


def validate_student_data(data, required_fields=None):
    """
    Validate student data.

    Args:
        data: Dictionary containing student data
        required_fields: List of required field names (optional)

    Returns:
        dict: Validated data

    Raises:
        ValidationError: If validation fails
    """
    if required_fields is None:
        required_fields = ['name', 'gender', 'education', 'id_card', 'phone',
                          'company', 'company_address', 'job_category']

    errors = {}

    # Check required fields
    for field in required_fields:
        if not data.get(field):
            errors[field] = '必填项'

    # Validate gender
    if 'gender' in data and data.get('gender') not in ['男', '女']:
        errors['gender'] = '性别须为"男"或"女"'

    # Validate ID card
    if 'id_card' in data:
        id_card = data.get('id_card', '')
        if id_card and not re.fullmatch(r'\d{17}[\dXx]', id_card):
            errors['id_card'] = '身份证号格式不正确'

    # Validate phone
    if 'phone' in data:
        phone = data.get('phone', '')
        if phone and not re.fullmatch(r'\d{11}', phone):
            errors['phone'] = '手机号格式不正确'

    if errors:
        raise ValidationError('validation_failed', fields=errors)

    return data


def validate_file_upload(file, allowed_extensions=None):
    """
    Validate uploaded file.

    Args:
        file: FileStorage object from request.files
        allowed_extensions: Set of allowed file extensions

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If validation fails
    """
    if allowed_extensions is None:
        allowed_extensions = {'jpg', 'jpeg', 'png'}

    allowed_mimetypes = {'image/jpeg', 'image/png'}
    max_size_mb = 10

    if not file or not file.filename:
        raise ValidationError('未选择文件')

    # Check file extension
    if '.' not in file.filename:
        raise ValidationError('文件名无效')

    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(f'不支持的文件类型，仅支持: {", ".join(allowed_extensions)}')

    mimetype = (file.mimetype or '').lower()
    if mimetype and mimetype not in allowed_mimetypes:
        raise ValidationError('文件MIME类型无效，仅支持 JPG/PNG 图片')

    file_size = getattr(file, 'content_length', None) or 0
    if not file_size:
        try:
            current_pos = file.stream.tell()
            file.stream.seek(0, 2)
            file_size = file.stream.tell()
            file.stream.seek(current_pos)
        except Exception:
            file_size = 0

    if file_size and file_size > max_size_mb * 1024 * 1024:
        raise ValidationError(f'文件大小不能超过 {max_size_mb}MB')

    return True
