import cv2
import numpy as np
from PIL import Image
from rembg import remove, new_session
import io  # 补充导入io模块，之前代码遗漏了这行
def change_id_photo_bg(input_path, output_path, bg_color=(255, 255, 255)):
    """
    将证件照背景替换为指定颜色（默认白色），优化衣服边缘识别问题
    
    参数:
        input_path: 输入证件照的路径（如 "input.jpg"）
        output_path: 处理后图片的保存路径（如 "output.jpg"）
        bg_color: 背景颜色，默认白色 (255,255,255)
    """
    try:
        # 1. 配置rembg会话，启用alpha抠图优化边缘
        # 设置alpha_matting参数提升边缘精度，避免误抠衣服
        session = new_session(
            model_name="u2net_human_seg",  # 专门针对人像分割的模型，更精准
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_size=10
        )

        # 2. 读取图片并精准抠图
        with open(input_path, "rb") as f:
            input_img = f.read()
        # 使用优化参数移除背景
        output_img = remove(input_img, session=session)
        img_no_bg = Image.open(io.BytesIO(output_img)).convert("RGBA")

        # 3. 修复抠图蒙版，避免衣服区域缺失
        # 将PIL图片转为OpenCV格式处理蒙版
        img_np = np.array(img_no_bg)
        # 提取alpha通道（透明度通道）
        alpha_channel = img_np[:, :, 3]
        
        # 创建膨胀核，让蒙版轻微膨胀，填补衣服边缘的漏洞
        kernel = np.ones((3, 3), np.uint8)
        alpha_channel = cv2.dilate(alpha_channel, kernel, iterations=1)
        # 将修复后的alpha通道放回原图
        img_np[:, :, 3] = alpha_channel
        img_no_bg_fixed = Image.fromarray(img_np, mode="RGBA")

        # 4. 创建纯白色背景并合成
        bg_img = Image.new("RGBA", img_no_bg_fixed.size, bg_color + (255,))
        result = Image.alpha_composite(bg_img, img_no_bg_fixed)
        result = result.convert("RGB")

        # 5. 保存图片
        result.save(output_path, quality=95)
        print(f"处理完成！图片已保存至: {output_path}")
        
    except Exception as e:
        print(f"处理失败：{str(e)}")
# ========== 调用示例 ==========
if __name__ == "__main__":
    # 替换成你的证件照路径
    input_photo = "training_system/uploads/140322198004088697黄娜-个人照片.jpg"
    # 处理后保存的路径
    output_photo = "training_system/uploads/140322198004088697黄娜-个人照片-white-bg.jpg"
    
    # 执行背景替换（默认白色）
    change_id_photo_bg(input_photo, output_photo)