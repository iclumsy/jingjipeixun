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
                          'job_category', 'exam_category']

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
        allowed_extensions = {'jpg', 'jpeg', 'png', 'pdf', 'docx'}

    if not file or not file.filename:
        raise ValidationError('未选择文件')

    # Check file extension
    if '.' not in file.filename:
        raise ValidationError('文件名无效')

    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(f'不支持的文件类型，仅支持: {", ".join(allowed_extensions)}')

    return True
