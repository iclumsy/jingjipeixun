"""Export routes for data export functionality."""
from flask import Blueprint, request, jsonify, send_file, current_app
from models.student import get_students
import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter


export_bp = Blueprint('export', __name__)


@export_bp.route('/api/export/excel', methods=['GET'])
def export_excel():
    """Export students data to Excel."""
    try:
        # Get query parameters
        status = request.args.get('status', '')
        company = request.args.get('company', '')

        # Get students
        training_type = request.args.get('training_type', '')
        students = get_students(status, '', company, training_type)

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "学员信息"

        # Define headers
        headers = [
            'ID', '姓名', '性别', '文化程度', '毕业院校', '所学专业',
            '身份证号', '手机号', '单位名称', '单位地址',
            '作业类别', '操作项目', '项目代号',
            '状态', '创建时间'
        ]

        # Add headers
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

        # Add data rows
        for row_num, student in enumerate(students, 2):
            status_text = '已审核' if student['status'] == 'reviewed' else '未审核'

            data = [
                student['id'],
                student['name'],
                student['gender'],
                student['education'],
                student.get('school', ''),
                student.get('major', ''),
                student['id_card'],
                student['phone'],
                student.get('company', ''),
                student.get('company_address', ''),
                student['job_category'],
                student.get('exam_project', ''),
                student.get('project_code', ''),
                status_text,
                student.get('created_at', '')
            ]

            for col_num, value in enumerate(data, 1):
                cell = ws.cell(row=row_num, column=col_num, value=str(value) if value is not None else '')
                cell.alignment = Alignment(horizontal='left', vertical='center')
                cell.border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )

        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)

            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass

            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

        # Save to BytesIO
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        current_app.logger.info(f'Excel export generated with {len(students)} students')

        # Return Excel file
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'学员信息_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )

    except Exception as e:
        current_app.logger.error(f'Error exporting to Excel: {str(e)}')
        return jsonify({'error': str(e)}), 500
