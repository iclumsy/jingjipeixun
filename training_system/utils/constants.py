FILE_MAP = {
    'photo': 'photo_path',
    'diploma': 'diploma_path',
    'id_card_front': 'id_card_front_path',
    'id_card_back': 'id_card_back_path',
    'hukou_residence': 'hukou_residence_path',
    'hukou_personal': 'hukou_personal_path'
}

ATTACHMENT_KEYS = [
    'photo_path', 'diploma_path',
    'id_card_front_path', 'id_card_back_path',
    'hukou_residence_path', 'hukou_personal_path',
    'training_form_path'
]

ALLOWED_TEXT_FIELDS = [
    'name', 'gender', 'education', 'school', 'major', 'id_card', 'phone',
    'company', 'company_address', 'job_category', 'exam_project', 'project_code', 'training_type'
]

REQUIRED_FIELDS = ['name', 'gender', 'education', 'id_card', 'phone',
                   'company', 'company_address', 'job_category']

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
