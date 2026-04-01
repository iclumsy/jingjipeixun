import os
import io
import shutil
import cv2
import numpy as np
from PIL import Image

A4_WIDTH = 2480
A4_HEIGHT = 3508
CM_IN_PX = 118 # roughly 300 DPI (1 inch = 2.54 cm -> 2.54cm / 300 ~ 118 pixels/cm)

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    
    return rect

def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
    
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    
    return warped

def auto_crop_document(image, expand_px=20):
    """尝试自动寻找边缘裁边并做水平校正。如果不成功则返回原图。"""
    try:
        orig = image.copy()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(gray, 75, 200)

        # 因为边缘很多是直线的，使用形态学闭运算可以连接断裂的直线边缘，让轮廓更清晰
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edged = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, kernel)

        # 改用 RETR_EXTERNAL 只获取最外层轮廓，彻底忽略材料内部的直线或表格框线
        cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]
        
        screenCnt = None
        for c in cnts:
            # 用凸包 (Convex Hull) 把轮廓“包裹”起来，保证取到的是绝对最靠外的顶点
            hull = cv2.convexHull(c)
            peri = cv2.arcLength(hull, True)
            approx = cv2.approxPolyDP(hull, 0.02 * peri, True)
            if len(approx) == 4:
                screenCnt = approx
                break

        # 如果找到四边形且面积占比大于 10%，执行透视变换
        if screenCnt is not None and cv2.contourArea(screenCnt) > 0.1 * image.shape[0] * image.shape[1]:
            pts = screenCnt.reshape(4, 2)
            
            # 将 4 个点排好序
            rect = order_points(pts)
            
            # 边缘往外扩 expand_px 个像素
            expanded = np.zeros_like(rect)
            # tl: 往左上扩
            expanded[0] = rect[0] + [-expand_px, -expand_px]
            # tr: 往右上扩
            expanded[1] = rect[1] + [expand_px, -expand_px]
            # br: 往右下扩
            expanded[2] = rect[2] + [expand_px, expand_px]
            # bl: 往左下扩
            expanded[3] = rect[3] + [-expand_px, expand_px]
            
            # 限制不能超出原图边界
            h, w = image.shape[:2]
            expanded[:, 0] = np.clip(expanded[:, 0], 0, w - 1)
            expanded[:, 1] = np.clip(expanded[:, 1], 0, h - 1)
            
            warped = four_point_transform(orig, expanded)
            return warped
    except Exception as e:
        print("Auto crop error:", e)
    return image

def read_cv_image(path):
    img_np = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(img_np, cv2.IMREAD_COLOR)

def write_cv_image(path, img, quality=95):
    ret, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if ret:
        with open(path, 'wb') as f:
            buf.tofile(f)

def create_a4_canvas():
    return np.full((A4_HEIGHT, A4_WIDTH, 3), 255, dtype=np.uint8)

def process_personal_photo(input_path, output_dir, name_prefix):
    """个人照片处理为 1MB 以下"""
    try:
        img = Image.open(input_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        output_path = os.path.join(output_dir, f"{name_prefix}-个人照片.jpg")
        
        quality = 95
        while True:
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality)
            size_kb = len(buffer.getvalue()) / 1024
            if size_kb < 1000 or quality <= 30:
                with open(output_path, 'wb') as f:
                    f.write(buffer.getvalue())
                break
            quality -= 10
            
    except Exception as e:
        print("Error processing personal photo:", e)

def process_diploma(input_path, output_dir, name_prefix):
    """学历证书照片，裁边，A4白色底，水平居中，宽两边留 1cm，水平校正"""
    try:
        img = read_cv_image(input_path)
        if img is None: return
        img = auto_crop_document(img)
        
        target_width = A4_WIDTH - 2 * CM_IN_PX
        h, w = img.shape[:2]
        target_height = int(h * (target_width / w))
        
        img_resized = cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_AREA)
        
        canvas = create_a4_canvas()
        x_offset = CM_IN_PX
        y_offset = max(0, (A4_HEIGHT - target_height) // 2)
        
        canvas_h = canvas.shape[0]
        if y_offset + target_height > canvas_h:
            target_height = canvas_h - y_offset
            img_resized = img_resized[:target_height, :]
            
        canvas[y_offset:y_offset+target_height, x_offset:x_offset+target_width] = img_resized
        
        output_path = os.path.join(output_dir, f"{name_prefix}-学历证书.jpg")
        write_cv_image(output_path, canvas)
    except Exception as e:
        print("Error processing diploma:", e)

def process_id_cards(front_path, back_path, output_dir, name_prefix):
    try:
        canvas = create_a4_canvas()
        
        target_width = A4_WIDTH // 2 
        x_offset = (A4_WIDTH - target_width) // 2
        
        front_img, back_img = None, None
        front_h, back_h = 0, 0
        
        if front_path and os.path.exists(front_path):
            front_img = read_cv_image(front_path)
            if front_img is not None:
                front_img = auto_crop_document(front_img)
                h, w = front_img.shape[:2]
                front_h = int(h * (target_width / w))
                front_img = cv2.resize(front_img, (target_width, front_h), interpolation=cv2.INTER_AREA)
                
        if back_path and os.path.exists(back_path):
            back_img = read_cv_image(back_path)
            if back_img is not None:
                back_img = auto_crop_document(back_img)
                h, w = back_img.shape[:2]
                back_h = int(h * (target_width / w))
                back_img = cv2.resize(back_img, (target_width, back_h), interpolation=cv2.INTER_AREA)
                
        gap = max(front_h, back_h) // 2
        total_height = front_h + back_h + gap
        
        if front_img is not None and back_img is not None:
            y_front = (A4_HEIGHT - total_height) // 2
            y_back = y_front + front_h + gap
            canvas[y_front:y_front+front_h, x_offset:x_offset+target_width] = front_img
            canvas[y_back:y_back+back_h, x_offset:x_offset+target_width] = back_img
        elif front_img is not None:
            y_front = (A4_HEIGHT - front_h) // 2
            canvas[y_front:y_front+front_h, x_offset:x_offset+target_width] = front_img
        elif back_img is not None:
            y_back = (A4_HEIGHT - back_h) // 2
            canvas[y_back:y_back+back_h, x_offset:x_offset+target_width] = back_img
            
        if front_img is not None or back_img is not None:
            output_path = os.path.join(output_dir, f"{name_prefix}-身份证.jpg")
            write_cv_image(output_path, canvas)
    except Exception as e:
        print("Error processing ID cards:", e)

def process_hukou(residence_path, personal_path, output_dir, name_prefix):
    try:
        canvas = create_a4_canvas()
        
        target_width = A4_WIDTH - 2 * 2 * CM_IN_PX # 两边空2cm 
        x_offset = 2 * CM_IN_PX
        
        img1, img2 = None, None
        h1, h2 = 0, 0
        
        if residence_path and os.path.exists(residence_path):
            img1 = read_cv_image(residence_path)
            if img1 is not None:
                img1 = auto_crop_document(img1, expand_px=50)
                h, w = img1.shape[:2]
                h1 = int(h * (target_width / w))
                img1 = cv2.resize(img1, (target_width, h1), interpolation=cv2.INTER_AREA)
                
        if personal_path and os.path.exists(personal_path):
            img2 = read_cv_image(personal_path)
            if img2 is not None:
                img2 = auto_crop_document(img2, expand_px=50)
                h, w = img2.shape[:2]
                h2 = int(h * (target_width / w))
                img2 = cv2.resize(img2, (target_width, h2), interpolation=cv2.INTER_AREA)
                
        gap = CM_IN_PX # 中间空1cm
        total_height = h1 + h2 + gap
        
        if img1 is not None and img2 is not None:
            y_start = (A4_HEIGHT - total_height) // 2
            canvas[y_start:y_start+h1, x_offset:x_offset+target_width] = img1
            canvas[y_start+h1+gap:y_start+h1+gap+h2, x_offset:x_offset+target_width] = img2
        elif img1 is not None:
            y_start = (A4_HEIGHT - h1) // 2
            canvas[y_start:y_start+h1, x_offset:x_offset+target_width] = img1
        elif img2 is not None:
            y_start = (A4_HEIGHT - h2) // 2
            canvas[y_start:y_start+h2, x_offset:x_offset+target_width] = img2
            
        if img1 is not None or img2 is not None:
            output_path = os.path.join(output_dir, f"{name_prefix}-户口本.jpg")
            write_cv_image(output_path, canvas)
    except Exception as e:
        print("Error processing hukou:", e)

def copy_health_form(form_path, output_dir, name_prefix):
    if form_path and os.path.exists(form_path):
        ext = os.path.splitext(form_path)[1]
        output_path = os.path.join(output_dir, f"{name_prefix}-体检表{ext}")
        shutil.copy2(form_path, output_path)

def generate_student_materials(student, base_dir, output_root):
    """
    入口函数，生成学员打包资料
    student: dictionary of student info
    """
    id_card = student.get('id_card', '')
    name = student.get('name', '')
    name_prefix = f"{id_card}-{name}"
    
    output_dir = os.path.join(output_root, f"{name_prefix}-报名材料")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        
    def get_abs_path(key):
        rel = student.get(key)
        return os.path.join(base_dir, rel) if rel else None
    
    photo_path = get_abs_path('photo_path')
    if photo_path and os.path.exists(photo_path):
        process_personal_photo(photo_path, output_dir, name_prefix)
        
    diploma_path = get_abs_path('diploma_path')
    if diploma_path and os.path.exists(diploma_path):
        process_diploma(diploma_path, output_dir, name_prefix)
        
    id_card_front_path = get_abs_path('id_card_front_path')
    id_card_back_path = get_abs_path('id_card_back_path')
    if (id_card_front_path and os.path.exists(id_card_front_path)) or \
       (id_card_back_path and os.path.exists(id_card_back_path)):
        process_id_cards(id_card_front_path, id_card_back_path, output_dir, name_prefix)
        
    hukou_residence_path = get_abs_path('hukou_residence_path')
    hukou_personal_path = get_abs_path('hukou_personal_path')
    if (hukou_residence_path and os.path.exists(hukou_residence_path)) or \
       (hukou_personal_path and os.path.exists(hukou_personal_path)):
        process_hukou(hukou_residence_path, hukou_personal_path, output_dir, name_prefix)
        
    training_form_path = get_abs_path('training_form_path')
    if training_form_path and os.path.exists(training_form_path):
        copy_health_form(training_form_path, output_dir, name_prefix)
        
    return output_dir
