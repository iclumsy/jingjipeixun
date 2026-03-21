import os
import sqlite3

def cleanup_orphaned_images():
    # 获取项目根目录 /Users/ditto/Documents/jingjipeixun/training_system
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'database/students.db')
    students_folder = os.path.join(base_dir, 'students')
    
    # 1. 把数据库里所有被引用过的图片路径全提取出来，放入白名单集合
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    records = conn.execute("SELECT photo_path, diploma_path, id_card_front_path, id_card_back_path, hukou_residence_path, hukou_personal_path FROM students").fetchall()
    conn.close()
    
    # 构建所有有效路径的绝对路径集合 Set
    valid_paths = set()
    for row in records:
        for path in dict(row).values():
            if path:
                # 统一拼装为操作系统的真实绝对路径
                valid_paths.add(os.path.abspath(os.path.join(base_dir, path)))

    freed_mb = 0
    deleted_count = 0
    
    # 2. 遍历咱们服务器硬盘上的 /students/ 文件夹
    if not os.path.exists(students_folder):
        print("📁 附件文件夹尚不存在，无需清理。")
        return

    for root, dirs, files in os.walk(students_folder):
        for file in files:
            # 忽略隐藏文件，比如 .DS_Store
            if file.startswith('.'):
                continue
                
            file_abs_path = os.path.abspath(os.path.join(root, file))
            # 3. 如果物理文件完全不在咱们的数据库白名单里，格杀勿论
            if file_abs_path not in valid_paths:
                file_size = os.path.getsize(file_abs_path)
                freed_mb += file_size / (1024 * 1024)
                try:
                    os.remove(file_abs_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ 删除文件失败: {file_abs_path}, 原因: {e}")
                
    print(f"✅ 清理完成！共清扫掉 {deleted_count} 个半途而废的孤儿文件/历史垃圾，为您服务器腾出 {freed_mb:.2f} MB 空间！")

if __name__ == '__main__':
    cleanup_orphaned_images()
