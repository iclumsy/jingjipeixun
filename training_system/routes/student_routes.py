"""Student-related routes."""
from flask import Blueprint, request, jsonify, current_app
from models.student import (
    create_student, get_students, get_student_by_id, update_student,
    delete_student, delete_students_batch, approve_student, approve_students_batch,
    get_companies
)
from services.image_service import process_and_save_file, delete_student_files
from services.document_service import generate_word_doc
from utils.validators import validate_student_data
from utils.error_handlers import ValidationError, NotFoundError
import os
import io
import zipfile


student_bp = Blueprint('student', __name__)


@student_bp.route('/api/students', methods=['POST'])
def create_student_route():
    """Create a new student."""
    try:
        data = request.form
        files = request.files

        # Validate data
        validate_student_data(data)

        # Save files
        file_paths = {}
        file_map = {
            'photo': 'photo_path',
            'diploma': 'diploma_path',
            'cert_front': 'cert_front_path',
            'cert_back': 'cert_back_path',
            'id_card_front': 'id_card_front_path',
            'id_card_back': 'id_card_back_path'
        }

        id_card_val = data.get('id_card', '').strip()
        company_val = data.get('company', '').strip()

        for input_name, db_key in file_map.items():
            file = files.get(input_name)
            if file and file.filename and id_card_val:
                try:
                    rel = process_and_save_file(
                        file, id_card_val, data.get('name', ''),
                        input_name, company_val
                    )
                    file_paths[db_key] = rel
                except Exception as e:
                    current_app.logger.error(f'Failed to save file {input_name}: {str(e)}')
                    file_paths[db_key] = ""
            else:
                file_paths[db_key] = ""

        file_paths['training_form_path'] = ""

        # Create student
        student_id = create_student(data, file_paths)
        current_app.logger.info(f'Student created: ID={student_id}')

        return jsonify({'message': 'Student added successfully', 'id': student_id}), 201

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error creating student: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students', methods=['GET'])
def get_students_route():
    """Get students with optional filters."""
    try:
        status = request.args.get('status', 'unreviewed')
        search = request.args.get('search', '')
        company = request.args.get('company', '')

        students = get_students(status, search, company)
        return jsonify(students)

    except Exception as e:
        current_app.logger.error(f'Error getting students: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/<int:id>', methods=['PUT', 'PATCH'])
def update_student_route(id):
    """Update a student."""
    try:
        allowed_text = [
            'name', 'gender', 'education', 'school', 'major', 'id_card', 'phone',
            'company', 'company_address', 'job_category', 'exam_project', 'exam_code'
        ]
        file_map = {
            'photo': 'photo_path',
            'diploma': 'diploma_path',
            'cert_front': 'cert_front_path',
            'cert_back': 'cert_back_path',
            'id_card_front': 'id_card_front_path',
            'id_card_back': 'id_card_back_path'
        }

        current_student = get_student_by_id(id)
        updates = {}

        # Handle form data (multipart) or JSON
        if request.form:
            data = request.form
            for k in allowed_text:
                if k in data:
                    updates[k] = data[k]

            # Validate partial update
            if updates:
                validate_student_data(updates, required_fields=[])

            # Handle file uploads
            for input_name, db_key in file_map.items():
                f = request.files.get(input_name)
                if f and f.filename:
                    id_card_for_name = data.get('id_card', current_student['id_card'])
                    name_for_save = data.get('name', current_student['name'])
                    company_for_name = data.get('company', current_student.get('company', ''))

                    # Delete old file
                    old_rel = current_student.get(db_key)
                    if old_rel:
                        delete_student_files({db_key: old_rel}, current_app.config['BASE_DIR'])

                    try:
                        rel = process_and_save_file(
                            f, id_card_for_name, name_for_save, input_name, company_for_name
                        )
                        updates[db_key] = rel
                    except Exception as e:
                        current_app.logger.error(f'Failed to save file {input_name}: {str(e)}')
                        updates[db_key] = ''
        else:
            payload = request.get_json(silent=True) or {}
            for k in allowed_text:
                if k in payload:
                    updates[k] = payload[k]

            # Validate partial update
            if updates:
                validate_student_data(updates, required_fields=[])

        # Update student
        updated_student = update_student(id, updates)
        current_app.logger.info(f'Student updated: ID={id}')

        return jsonify(updated_student)

    except (ValidationError, NotFoundError) as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error updating student {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/<int:id>/reject', methods=['POST'])
def reject_student_route(id):
    """Reject and delete a student."""
    try:
        student = delete_student(id)

        # Delete files
        delete_student_files(student, current_app.config['BASE_DIR'])

        current_app.logger.info(f'Student rejected and deleted: ID={id}')
        return jsonify({'message': 'Student rejected and deleted'})

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error rejecting student {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/<int:id>/approve', methods=['POST'])
def approve_student_route(id):
    """Approve a student."""
    try:
        student = approve_student(id)
        current_app.logger.info(f'Student approved: ID={id}')
        return jsonify(student)

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error approving student {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/<int:id>/generate', methods=['POST'])
def generate_materials_route(id):
    """Generate training materials for a student."""
    try:
        student = get_student_by_id(id)

        # Create student folder
        student_folder_name = f"{student['company']}-{student['name']}"
        student_folder_path = os.path.join(
            current_app.config['STUDENTS_FOLDER'],
            student_folder_name
        )
        os.makedirs(student_folder_path, exist_ok=True)

        # Generate document
        doc_path = os.path.join(
            student_folder_path,
            f"{student['id_card']}{student['name']}-体检表.docx"
        )

        photo_abs_path = None
        if student.get('photo_path'):
            if student['photo_path'].startswith('students/'):
                photo_abs_path = os.path.join(current_app.config['BASE_DIR'], student['photo_path'])
            else:
                filename = os.path.basename(student['photo_path'])
                photo_abs_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        generate_word_doc(
            current_app.config['TEMPLATE_PATH'],
            doc_path,
            student,
            photo_abs_path
        )

        # Update database
        rel_path = f"students/{student_folder_name}/{os.path.basename(doc_path)}"
        update_student(id, {'training_form_path': rel_path})

        download_url = f"/students/{student_folder_name}/{os.path.basename(doc_path)}"
        current_app.logger.info(f'Materials generated for student ID={id}')

        return jsonify({
            'message': 'materials generated',
            'download_url': download_url,
            'path': rel_path
        })

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error generating materials for student {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/<int:id>/attachments.zip', methods=['GET'])
def download_attachments_zip_route(id):
    """Download all attachments for a student as ZIP."""
    try:
        student = get_student_by_id(id)

        if student.get('status') != 'reviewed':
            return jsonify({'error': '仅支持已审核学员打包下载'}), 400

        attachment_keys = [
            'photo_path', 'diploma_path', 'cert_front_path', 'cert_back_path',
            'id_card_front_path', 'id_card_back_path', 'training_form_path'
        ]

        files_to_zip = []
        for key in attachment_keys:
            rel = student.get(key, '')
            if not rel:
                continue
            abs_path = os.path.join(current_app.config['BASE_DIR'], rel)
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                arcname = os.path.basename(abs_path)
                files_to_zip.append((abs_path, arcname))

        if not files_to_zip:
            return jsonify({'error': '该学员暂无可打包的附件'}), 400

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            for abs_path, arcname in files_to_zip:
                try:
                    zf.write(abs_path, arcname)
                except Exception as e:
                    current_app.logger.error(f'Failed to add file to ZIP: {str(e)}')

        buffer.seek(0)

        from flask import send_file
        safe_name = f"{student.get('id_card','')}-{student.get('name','')}".replace('/', '-').replace('\\', '-')
        current_app.logger.info(f'Attachments ZIP generated for student ID={id}')

        return send_file(
            buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{safe_name}.zip"
        )

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error generating ZIP for student {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/batch/approve', methods=['POST'])
def batch_approve_students_route():
    """Batch approve students."""
    try:
        data = request.get_json()
        if not data or 'ids' not in data:
            raise ValidationError('Missing student IDs')

        ids = data['ids']
        if not isinstance(ids, list):
            raise ValidationError('IDs must be a list')

        approve_students_batch(ids)
        current_app.logger.info(f'Batch approved {len(ids)} students')

        return jsonify({'message': f'Successfully approved {len(ids)} students'}), 200

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error batch approving students: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/batch/reject', methods=['POST'])
def batch_reject_students_route():
    """Batch reject and delete students."""
    try:
        data = request.get_json()
        if not data or 'ids' not in data:
            raise ValidationError('Missing student IDs')

        ids = data['ids']
        if not isinstance(ids, list):
            raise ValidationError('IDs must be a list')

        students = delete_students_batch(ids)

        # Delete files for each student
        for student in students:
            delete_student_files(student, current_app.config['BASE_DIR'])

        current_app.logger.info(f'Batch rejected {len(ids)} students')
        return jsonify({'message': f'Successfully rejected and deleted {len(ids)} students'}), 200

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error batch rejecting students: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/batch/delete', methods=['POST'])
def batch_delete_students_route():
    """Batch delete students."""
    try:
        data = request.get_json()
        if not data or 'ids' not in data:
            raise ValidationError('Missing student IDs')

        ids = data['ids']
        if not isinstance(ids, list):
            raise ValidationError('IDs must be a list')

        students = delete_students_batch(ids)

        # Delete files for each student
        for student in students:
            delete_student_files(student, current_app.config['BASE_DIR'])

        current_app.logger.info(f'Batch deleted {len(ids)} students')
        return jsonify({'message': f'Successfully deleted {len(ids)} students'}), 200

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error batch deleting students: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/companies', methods=['GET'])
def get_companies_route():
    """Get distinct company names."""
    try:
        status = request.args.get('status', '')
        company_filter = request.args.get('company', '')

        companies = get_companies(status, company_filter)
        return jsonify(companies)

    except Exception as e:
        current_app.logger.error(f'Error getting companies: {str(e)}')
        return jsonify({'error': str(e)}), 500
