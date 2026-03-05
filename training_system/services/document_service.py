"""文档生成服务。"""
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


# 需要生成体检表的项目 -> 模板文件名映射
HEALTH_CHECK_TEMPLATES = {
    '叉车司机': '叉车司机体检表.docx',
    '锅炉水处理': '锅炉水处理体检表.docx'
}

# 项目代号 -> 体检表模板名称映射
HEALTH_CHECK_PROJECT_CODES = {
    'N1': '叉车司机',
    'G3': '锅炉水处理'
}


def needs_health_check(exam_project, project_code=''):
    """
    检查该操作项目是否需要生成体检表。
    
    参数:
        exam_project: 操作项目名称
        project_code: 项目代号（如 G3）
        
    返回:
        tuple: (needs_check: bool, template_key: str 或 None)
    """
    normalized_code = (project_code or '').strip().upper()
    if normalized_code in HEALTH_CHECK_PROJECT_CODES:
        return True, HEALTH_CHECK_PROJECT_CODES[normalized_code]

    if not exam_project:
        return False, None
    
    normalized_project = str(exam_project).strip()
    for key in HEALTH_CHECK_TEMPLATES.keys():
        if key in normalized_project:
            return True, key
    return False, None


def generate_health_check_form(student, base_dir, students_folder):
    """
    为符合条件的学员生成体检表。
    
    参数:
        student: 学员数据字典
        base_dir: 基础目录路径
        students_folder: 学员文件夹路径
        
    返回:
        str: 生成文件的相对路径，不需要时返回 None
    """
    exam_project = student.get('exam_project', '')
    project_code = student.get('project_code', '')
    needs_check, template_key = needs_health_check(exam_project, project_code)
    
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
        photo_abs_path = os.path.join(base_dir, student['photo_path'])
    
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
    根据模板生成填写学员数据的 Word 文档。

    参数:
        template_path: 模板文档路径
        output_path: 输出文档保存路径
        data: 包含学员数据的字典
        photo_path: 学员照片路径（可选）
    """
    try:
        doc = Document(template_path)

        # 1. 文本替换（保留原样式）
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
                        # 查找相邻的下一个单元格
                        if i + 1 < len(row.cells):
                            target_cell = row.cells[i+1]

                            # 安全检查：不覆盖也是标签的单元格
                            if target_cell.text.strip() in replacements:
                                continue

                            new_val = replacements[text]

                            # 替换第一个 run 中的文本以保留格式
                            if target_cell.paragraphs:
                                p = target_cell.paragraphs[0]
                                if p.runs:
                                    p.runs[0].text = new_val
                                    # 清除其他 run
                                    for r in p.runs[1:]:
                                        r.text = ''
                                else:
                                    p.add_run(new_val)

                                # 清除其他段落
                                for p in target_cell.paragraphs[1:]:
                                    p.clear()
                            else:
                                target_cell.text = new_val

        # 2. 图片替换
        if photo_path and os.path.exists(photo_path):
            _insert_photo_into_doc(doc, photo_path)

        doc.save(output_path)
        current_app.logger.info(f'Document generated: {output_path}')

    except Exception as e:
        current_app.logger.error(f'Failed to generate document: {str(e)}')
        raise


def _insert_photo_into_doc(doc, photo_path):
    """
    将照片插入到 Word 文档中。

    参数:
        doc: Document 对象
        photo_path: 照片文件路径
    """
    try:
        # 处理照片背景
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

        # 加载照片
        with open(photo_to_use, 'rb') as f:
            img_bytes = f.read()

        # 默认目标尺寸（一寸证件照 2.5x3.5cm）
        default_w_in = 2.5 / 2.54  # ~0.984in
        default_h_in = 3.5 / 2.54  # ~1.378in

        # 尝试插入到表格单元格
        replaced = False
        target_cell = None
        found_table = None
        found_col_idx = None

        # 查找包含 “照片” 或 “照” 的单元格
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

        # 备选：第一个表格的右上角单元格
        if not target_cell and len(doc.tables) > 0:
            tbl = doc.tables[0]
            target_cell = tbl.cell(0, len(tbl.rows[0].cells)-1)
            found_table = tbl
            found_col_idx = len(tbl.rows[0].cells)-1

        if target_cell:
            # 确定目标单元格尺寸
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
                # 备选：使用 gridCol 宽度
                try:
                    tbl_root = etree.fromstring(found_table._tbl.xml.encode('utf-8'))
                    gridCols = tbl_root.xpath('.//w:tblGrid/w:gridCol', namespaces=ns)
                    if gridCols and found_col_idx is not None and found_col_idx < len(gridCols):
                        gv = int(gridCols[found_col_idx].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w'))
                        target_w_in = gv / 1440.0
                except Exception:
                    pass

            # 校验目标宽度
            if not target_w_in or target_w_in <= 0 or target_w_in > 20:
                target_w_in = default_w_in

            tgt_w = target_w_in
            tgt_h = tgt_w * (3.5 / 2.5)  # 证件照纵横比

            # 确保最小尺寸
            min_w_in = 0.6
            min_h_in = 0.8
            if tgt_w < min_w_in:
                tgt_w = min_w_in
            if tgt_h < min_h_in:
                tgt_h = min_h_in

            # 调整尺寸并裁剪图片
            try:
                src_img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                src_w, src_h = src_img.size

                # 缩放以适应目标区域
                dpi = 300
                px_w = max(120, int(tgt_w * dpi))
                px_h = max(160, int(tgt_h * dpi))
                scale = min(px_w / src_w, px_h / src_h)
                new_w = max(1, int(src_w * scale))
                new_h = max(1, int(src_h * scale))
                resized_img = src_img.resize((new_w, new_h), Image.LANCZOS)

                # 粘贴到白色画布上
                canvas = Image.new('RGB', (px_w, px_h), (255, 255, 255))
                paste_left = (px_w - new_w) // 2
                paste_top = (px_h - new_h) // 2
                canvas.paste(resized_img, (paste_left, paste_top))

                out_bio = io.BytesIO()
                canvas.save(out_bio, format='JPEG', quality=95)
                img_bytes_final = out_bio.getvalue()

                # 清除已有段落并插入图片
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

        # 备选：替换现有的图片关系
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

            # 搜索段落中的 r:embed
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
        # 清理临时文件
        if temp_photo_path and os.path.exists(temp_photo_path):
            try:
                os.remove(temp_photo_path)
            except Exception:
                pass
