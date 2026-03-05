"""
数据校验工具。

本模块提供学员数据和文件上传的服务端校验功能。

校验规则:
    学员数据:
        - 必填字段: 姓名、性别、文化程度、身份证号、手机号、单位名称、单位地址、作业类别
        - 性别仅允许 "男" 或 "女"
        - 身份证号必须为 17 位数字 + 1 位数字或X
        - 手机号必须为 11 位数字

    文件上传:
        - 仅允许 JPG/PNG 图片
        - 单文件最大 10MB
        - 同时校验扩展名和 MIME 类型（双重校验防止文件伪造）
"""
import re
from utils.error_handlers import ValidationError


def validate_student_data(data, required_fields=None):
    """
    校验学员基本信息字段。

    支持两种模式:
    - 全量校验（默认）: 校验所有必填字段，用于创建学员
    - 部分校验: 传入 required_fields=[] 仅校验格式，用于更新学员

    参数:
        data: 包含学员数据的字典
        required_fields: 必填字段列表，传入 [] 可跳过必填校验

    返回:
        dict: 校验通过的原始数据

    异常:
        ValidationError: 校验失败时抛出，包含字段级别的错误信息
    """
    if required_fields is None:
        # 默认必填字段列表（创建学员时使用）
        required_fields = ['name', 'gender', 'education', 'id_card', 'phone',
                          'company', 'company_address', 'job_category']

    errors = {}

    # 检查必填字段
    for field in required_fields:
        if not data.get(field):
            errors[field] = '必填项'

    # 校验性别
    if 'gender' in data and data.get('gender') not in ['男', '女']:
        errors['gender'] = '性别须为"男"或"女"'

    # 校验身份证号（18位：17位数字 + 1位数字或X）
    if 'id_card' in data:
        id_card = data.get('id_card', '')
        if id_card and not re.fullmatch(r'\d{17}[\dXx]', id_card):
            errors['id_card'] = '身份证号格式不正确'

    # 校验手机号（11位数字）
    if 'phone' in data:
        phone = data.get('phone', '')
        if phone and not re.fullmatch(r'\d{11}', phone):
            errors['phone'] = '手机号格式不正确'

    if errors:
        raise ValidationError('validation_failed', fields=errors)

    return data


def validate_file_upload(file, allowed_extensions=None):
    """
    校验上传文件的格式和大小。

    执行三重校验:
    1. 文件扩展名白名单校验
    2. MIME 类型校验（防止文件伪造）
    3. 文件大小上限校验

    参数:
        file: 来自 request.files 的 FileStorage 对象
        allowed_extensions: 允许的文件扩展名集合（默认 jpg/jpeg/png）

    返回:
        bool: 校验通过返回 True

    异常:
        ValidationError: 校验失败时抛出
    """
    if allowed_extensions is None:
        allowed_extensions = {'jpg', 'jpeg', 'png'}

    # 允许的 MIME 类型白名单
    allowed_mimetypes = {'image/jpeg', 'image/png'}
    max_size_mb = 10  # 单文件最大 10MB

    if not file or not file.filename:
        raise ValidationError('未选择文件')

    # 检查文件扩展名
    if '.' not in file.filename:
        raise ValidationError('文件名无效')

    # 校验文件扩展名
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(f'不支持的文件类型，仅支持: {", ".join(allowed_extensions)}')

    # 校验 MIME 类型（双重校验防止篡改扩展名伪造文件类型）
    mimetype = (file.mimetype or '').lower()
    if mimetype and mimetype not in allowed_mimetypes:
        raise ValidationError('文件MIME类型无效，仅支持 JPG/PNG 图片')

    # 校验文件大小
    # content_length 可能不可用（取决于客户端是否发送 Content-Length 头）
    # 因此回退到读取文件流的实际大小
    file_size = getattr(file, 'content_length', None) or 0
    if not file_size:
        try:
            current_pos = file.stream.tell()   # 保存当前读取位置
            file.stream.seek(0, 2)             # 移到文件末尾
            file_size = file.stream.tell()     # 获取文件大小
            file.stream.seek(current_pos)      # 恢复原始位置
        except Exception:
            file_size = 0

    if file_size and file_size > max_size_mb * 1024 * 1024:
        raise ValidationError(f'文件大小不能超过 {max_size_mb}MB')

    return True
