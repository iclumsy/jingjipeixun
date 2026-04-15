import os
import sqlite3
import time


# 文件必须比这个时间更老才会被清理（避免误删刚上传但未提交的文件）
MIN_AGE_HOURS = 24


def get_valid_paths(db_path, base_dir):
    """从数据库中提取所有被引用的文件绝对路径作为白名单。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    records = conn.execute("""
        SELECT photo_path, diploma_path,
               id_card_front_path, id_card_back_path,
               hukou_residence_path, hukou_personal_path,
               training_form_path
        FROM students
    """).fetchall()
    conn.close()

    valid_paths = set()
    for row in records:
        for path in dict(row).values():
            if path:
                valid_paths.add(os.path.abspath(os.path.join(base_dir, path)))
    return valid_paths


def is_inside_materials_folder(file_abs_path):
    """判断文件是否位于生成的报名材料子文件夹中（不能删除）。"""
    # 报名材料文件夹命名格式：身份证号-姓名-报名材料
    parts = file_abs_path.replace('\\', '/').split('/')
    return any(part.endswith('-报名材料') for part in parts)


def cleanup_tmp_folder(students_folder, min_age_hours, dry_run):
    """清理 students/tmp/ 目录中超过指定时间的孤立临时文件（平铺结构）。"""
    tmp_root = os.path.join(students_folder, 'tmp')
    if not os.path.exists(tmp_root):
        return 0, 0.0

    now = time.time()
    min_age_seconds = min_age_hours * 3600
    deleted_files = 0
    freed_mb = 0.0

    for entry in os.listdir(tmp_root):
        fpath = os.path.join(tmp_root, entry)
        if not os.path.isfile(fpath):
            continue
        try:
            mtime = os.path.getmtime(fpath)
        except OSError:
            continue
        if (now - mtime) < min_age_seconds:
            continue

        try:
            freed_mb += os.path.getsize(fpath) / (1024 * 1024)
        except OSError:
            pass

        if dry_run:
            print(f"  [将删除临时文件] {fpath}")
        else:
            try:
                os.remove(fpath)
                deleted_files += 1
            except Exception as e:
                print(f"❌ 删除临时文件失败: {fpath}，原因: {e}")

    return deleted_files, freed_mb


def cleanup_empty_dirs(students_folder, dry_run):
    """递归清理 students/ 目录下的空文件夹。"""
    deleted_count = 0
    # topdown=False 确保从最深层开始往上删
    for root, dirs, files in os.walk(students_folder, topdown=False):
        # 保护：不要删除 students 根目录
        if os.path.abspath(root) == os.path.abspath(students_folder):
            continue

        # 保护：tmp 目录本身不要删
        if os.path.basename(root) == 'tmp':
            continue

        # 检查目录下是否还有文件或子目录
        remaining = [i for i in os.listdir(root) if not i.startswith('.')]
        if not remaining:
            if dry_run:
                print(f"  [将删除空文件夹] {root}")
            else:
                try:
                    os.rmdir(root)
                    deleted_count += 1
                except Exception:
                    pass
    return deleted_count


def cleanup_orphaned_images(dry_run=True, min_age_hours=MIN_AGE_HOURS):
    """
    清理 students/ 目录中不再被数据库引用的孤立文件。

    参数:
        dry_run      : True 时只打印将要删除的文件，不实际操作（默认开启，安全模式）
        min_age_hours: 文件最小存在时间（小时），防止误删刚上传的临时文件
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'database/students.db')
    students_folder = os.path.join(base_dir, 'students')

    if not os.path.exists(students_folder):
        print("📁 附件文件夹尚不存在，无需清理。")
        return

    if dry_run:
        print("⚠️  [DRY RUN 模式] 不会实际删除任何文件，仅列出将会被删除的内容。")
        print("    确认无误后，请以 --delete 参数再次运行。\n")

    valid_paths = get_valid_paths(db_path, base_dir)
    now = time.time()
    min_age_seconds = min_age_hours * 3600

    freed_mb = 0.0
    deleted_count = 0
    skipped_materials = 0
    skipped_young = 0

    for root, dirs, files in os.walk(students_folder):
        # 跳过隐藏目录和 tmp 目录（tmp 目录走单独清理逻辑）
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'tmp']

        for file in files:
            if file.startswith('.'):
                continue

            file_abs_path = os.path.abspath(os.path.join(root, file))

            # ✅ 保护：报名材料子文件夹中生成的处理图不在数据库里，绝不能删
            if is_inside_materials_folder(file_abs_path):
                skipped_materials += 1
                continue

            # ✅ 保护：已被数据库引用的文件不能删
            if file_abs_path in valid_paths:
                continue

            # ✅ 保护：文件太新，可能是还没提交的表单附件
            try:
                mtime = os.path.getmtime(file_abs_path)
            except OSError:
                continue
            if (now - mtime) < min_age_seconds:
                skipped_young += 1
                continue

            file_size = os.path.getsize(file_abs_path)
            freed_mb += file_size / (1024 * 1024)

            if dry_run:
                print(f"  [将删除] {file_abs_path}  ({file_size / 1024:.1f} KB)")
            else:
                try:
                    os.remove(file_abs_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ 删除失败: {file_abs_path}，原因: {e}")

    if dry_run:
        print(f"\n📊 预计将删除 {int(freed_mb * 1024 / 1024)} 个文件，释放约 {freed_mb:.2f} MB")
        print(f"   （已保护 {skipped_materials} 个报名材料文件，跳过 {skipped_young} 个刚上传的临时文件）")
    else:
        print(f"\n✅ 清理完成！删除 {deleted_count} 个孤立文件，释放 {freed_mb:.2f} MB")
        print(f"   （已保护 {skipped_materials} 个报名材料文件，跳过 {skipped_young} 个刚上传的临时文件）")

    # 清理 tmp/ 目录中超时的临时文件夹
    print(f"\n🗂  清理 students/tmp/ 目录（超过 {min_age_hours} 小时的孤立上传）...")
    tmp_files, tmp_mb = cleanup_tmp_folder(students_folder, min_age_hours, dry_run)
    if dry_run:
        print(f"   预计删除过期临时文件，释放约 {tmp_mb:.2f} MB")
    else:
        print(f"   删除 {tmp_files} 个过期临时文件，释放 {tmp_mb:.2f} MB")

    # 清理遗留的空文件夹
    print(f"\n📁 清理遗留空文件夹...")
    empty_dirs = cleanup_empty_dirs(students_folder, dry_run)
    if dry_run:
        print(f"   预计清理 {empty_dirs} 个潜在空文件夹")
    else:
        print(f"   已清理 {empty_dirs} 个空文件夹")


if __name__ == '__main__':
    import sys
    # 命令行传入 --delete 参数才真正删除，否则只走 dry-run 安全预览
    actually_delete = '--delete' in sys.argv
    cleanup_orphaned_images(dry_run=not actually_delete)
