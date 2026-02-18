FILE_MAP = {
    'photo': 'photo_path',
    'diploma': 'diploma_path',
    'cert_front': 'cert_front_path',
    'cert_back': 'cert_back_path',
    'id_card_front': 'id_card_front_path',
    'id_card_back': 'id_card_back_path'
}

ATTACHMENT_KEYS = [
    'photo_path', 'diploma_path', 'cert_front_path', 'cert_back_path',
    'id_card_front_path', 'id_card_back_path', 'training_form_path'
]

ALLOWED_TEXT_FIELDS = [
    'name', 'gender', 'education', 'school', 'major', 'id_card', 'phone',
    'company', 'company_address', 'job_category', 'exam_project', 'exam_code'
]

REQUIRED_FIELDS = ['name', 'gender', 'education', 'id_card', 'phone',
                   'job_category']

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf', 'docx'}
