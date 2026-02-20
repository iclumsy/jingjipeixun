"""Document generation service."""
import os
import io
import tempfile
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from PIL import Image
from lxml import etree
from flask import current_app
from services.image_service import change_id_photo_bg


HEALTH_CHECK_TEMPLATES = {
    '叉车司机': '叉车司机体检表.docx',
    '锅炉水处理': '锅炉水处理体检表.docx'
}


def needs_health_check(exam_project):
    """
    Check if the exam project requires a health check form.
    
    Args:
        exam_project: The exam project name
        
    Returns:
        tuple: (needs_check: bool, template_key: str or None)
    """
    if not exam_project:
        return False, None
    
    for key in HEALTH_CHECK_TEMPLATES.keys():
        if key in exam_project:
            return True, key
    return False, None


def generate_health_check_form(student, base_dir, students_folder):
    """
    Generate health check form for eligible students.
    
    Args:
        student: Student data dictionary
        base_dir: Base directory path
        students_folder: Students folder path
        
    Returns:
        str: Relative path to generated file, or None if not needed
    """
    exam_project = student.get('exam_project', '')
    needs_check, template_key = needs_health_check(exam_project)
    
    if not needs_check:
        return None
    
    template_name = HEALTH_CHECK_TEMPLATES.get(template_key)
    if not template_name:
        return None
    
    template_path = os.path.join(base_dir, template_name)
    if not os.path.exists(template_path):
        current_app.logger.warning(f'Health check template not found: {template_path}')
        return None
    
    training_type = student.get('training_type', 'special_operation')
    training_type_name = '特种作业' if training_type == 'special_operation' else '特种设备'
    student_folder_name = f"{training_type_name}-{student.get('company', '')}-{student['name']}"
    student_folder_path = os.path.join(students_folder, student_folder_name)
    os.makedirs(student_folder_path, exist_ok=True)
    
    doc_path = os.path.join(
        student_folder_path,
        f"{student['id_card']}-{student['name']}-体检表.docx"
    )
    
    photo_abs_path = None
    if student.get('photo_path'):
        if student['photo_path'].startswith('students/'):
            photo_abs_path = os.path.join(base_dir, student['photo_path'])
        else:
            filename = os.path.basename(student['photo_path'])
            photo_abs_path = os.path.join(base_dir, 'uploads', filename)
    
    data = {
        'name': student['name'],
        'gender': student['gender'],
        'id_card': student['id_card']
    }
    
    generate_word_doc(template_path, doc_path, data, photo_abs_path)
    
    rel_path = f"students/{student_folder_name}/{os.path.basename(doc_path)}"
    return rel_path


def generate_word_doc(template_path, output_path, data, photo_path=None):
    """
    Generate Word document from template with student data.

    Args:
        template_path: Path to template document
        output_path: Path to save generated document
        data: Dictionary containing student data
        photo_path: Path to student photo (optional)
    """
    try:
        doc = Document(template_path)

        # 1. Text Replacement (Preserving Style)
        replacements = {
            '姓名': data.get('name', ''),
            '性别': data.get('gender', ''),
            '身份证号': data.get('id_card', ''),
        }

        for table in doc.tables:
            for row in table.rows:
                for i, cell in enumerate(row.cells):
                    text = cell.text.strip()
                    if text in replacements:
                        # Look for the next cell
                        if i + 1 < len(row.cells):
                            target_cell = row.cells[i+1]

                            # Safety check: Don't overwrite if target is also a label
                            if target_cell.text.strip() in replacements:
                                continue

                            new_val = replacements[text]

                            # Replace text in first run to preserve formatting
                            if target_cell.paragraphs:
                                p = target_cell.paragraphs[0]
                                if p.runs:
                                    p.runs[0].text = new_val
                                    # Clear other runs
                                    for r in p.runs[1:]:
                                        r.text = ''
                                else:
                                    p.add_run(new_val)

                                # Clear other paragraphs
                                for p in target_cell.paragraphs[1:]:
                                    p.clear()
                            else:
                                target_cell.text = new_val

        # 2. Image Replacement
        if photo_path and os.path.exists(photo_path):
            _insert_photo_into_doc(doc, photo_path)

        doc.save(output_path)
        current_app.logger.info(f'Document generated: {output_path}')

    except Exception as e:
        current_app.logger.error(f'Failed to generate document: {str(e)}')
        raise


def _insert_photo_into_doc(doc, photo_path):
    """
    Insert photo into Word document.

    Args:
        doc: Document object
        photo_path: Path to photo file
    """
    try:
        # Process photo background
        temp_photo_path = None
        try:
            temp_fd, temp_photo_path = tempfile.mkstemp(suffix='.jpg')
            os.close(temp_fd)
            processed_photo_path = change_id_photo_bg(photo_path, temp_photo_path)
            photo_to_use = processed_photo_path if processed_photo_path == temp_photo_path else photo_path
        except Exception as e:
            current_app.logger.warning(f'Background processing failed, using original: {str(e)}')
            photo_to_use = photo_path
            temp_photo_path = None

        # Load photo
        with open(photo_to_use, 'rb') as f:
            img_bytes = f.read()

        # Default target size (one-inch portrait 2.5x3.5cm)
        default_w_in = 2.5 / 2.54  # ~0.984in
        default_h_in = 3.5 / 2.54  # ~1.378in

        # Try inserting into table cell
        replaced = False
        target_cell = None
        found_table = None
        found_col_idx = None

        # Look for cell containing '照片' or '照'
        for ti, table in enumerate(doc.tables):
            for ri, row in enumerate(table.rows):
                for ci, cell in enumerate(row.cells):
                    txt = cell.text.strip()
                    if '照片' in txt or '照' in txt:
                        target_cell = cell
                        found_table = table
                        found_col_idx = ci
                        break
                if target_cell:
                    break
            if target_cell:
                break

        # Fallback: top-right cell of first table
        if not target_cell and len(doc.tables) > 0:
            tbl = doc.tables[0]
            target_cell = tbl.cell(0, len(tbl.rows[0].cells)-1)
            found_table = tbl
            found_col_idx = len(tbl.rows[0].cells)-1

        if target_cell:
            # Determine target cell size
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            try:
                cell_root = etree.fromstring(target_cell._tc.xml.encode('utf-8'))
            except Exception:
                cell_root = None

            tcW = None
            if cell_root is not None:
                tcW = cell_root.xpath('.//w:tcPr/w:tcW', namespaces=ns)

            target_w_in = default_w_in
            if tcW:
                try:
                    w_val = int(tcW[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w'))
                    w_type = tcW[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type')
                    if w_type == 'dxa':
                        target_w_in = w_val / 1440.0
                except Exception:
                    pass
            else:
                # Fallback to gridCol width
                try:
                    tbl_root = etree.fromstring(found_table._tbl.xml.encode('utf-8'))
                    gridCols = tbl_root.xpath('.//w:tblGrid/w:gridCol', namespaces=ns)
                    if gridCols and found_col_idx is not None and found_col_idx < len(gridCols):
                        gv = int(gridCols[found_col_idx].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w'))
                        target_w_in = gv / 1440.0
                except Exception:
                    pass

            # Validate target width
            if not target_w_in or target_w_in <= 0 or target_w_in > 20:
                target_w_in = default_w_in

            tgt_w = target_w_in
            tgt_h = tgt_w * (3.5 / 2.5)  # Portrait aspect ratio

            # Ensure minimum size
            min_w_in = 0.6
            min_h_in = 0.8
            if tgt_w < min_w_in:
                tgt_w = min_w_in
            if tgt_h < min_h_in:
                tgt_h = min_h_in

            # Resize and crop image
            try:
                src_img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                src_w, src_h = src_img.size

                # Resize to fit target box
                dpi = 300
                px_w = max(120, int(tgt_w * dpi))
                px_h = max(160, int(tgt_h * dpi))
                scale = min(px_w / src_w, px_h / src_h)
                new_w = max(1, int(src_w * scale))
                new_h = max(1, int(src_h * scale))
                resized_img = src_img.resize((new_w, new_h), Image.LANCZOS)

                # Paste onto white canvas
                canvas = Image.new('RGB', (px_w, px_h), (255, 255, 255))
                paste_left = (px_w - new_w) // 2
                paste_top = (px_h - new_h) // 2
                canvas.paste(resized_img, (paste_left, paste_top))

                out_bio = io.BytesIO()
                canvas.save(out_bio, format='JPEG', quality=95)
                img_bytes_final = out_bio.getvalue()

                # Clear existing paragraphs and insert image
                for p in list(target_cell.paragraphs):
                    p.clear()
                p = target_cell.paragraphs[0]
                try:
                    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                except Exception:
                    pass
                run = p.add_run()
                bio2 = io.BytesIO(img_bytes_final)
                try:
                    run.add_picture(bio2, width=Inches(tgt_w), height=Inches(tgt_h))
                except TypeError:
                    bio2.seek(0)
                    run.add_picture(bio2, width=Inches(tgt_w))
                replaced = True
            except Exception as e:
                current_app.logger.error(f'Error preparing/resizing picture: {str(e)}')

        # Fallback: replace existing image rels
        if not replaced:
            blip_rid = None
            for rel in doc.part.rels:
                try:
                    rel_obj = doc.part.rels[rel]
                    if getattr(rel_obj, 'reltype', '').endswith('/image') or \
                       'image' in getattr(rel_obj.target_part, '__class__', '').lower():
                        blip_rid = rel
                        break
                except Exception:
                    continue

            # Search paragraphs for r:embed
            if not blip_rid:
                import re
                for p in doc.paragraphs:
                    xml = p._element.xml
                    if 'r:embed="' in xml:
                        match = re.search(r'r:embed="([^\"]+)"', xml)
                        if match:
                            blip_rid = match.group(1)
                            break

            if blip_rid and blip_rid in doc.part.rels:
                try:
                    doc.part.rels[blip_rid].target_part._blob = img_bytes
                except Exception:
                    pass

    except Exception as e:
        current_app.logger.error(f'Error processing/replacing image: {str(e)}')
    finally:
        # Clean up temp file
        if temp_photo_path and os.path.exists(temp_photo_path):
            try:
                os.remove(temp_photo_path)
            except Exception:
                pass
