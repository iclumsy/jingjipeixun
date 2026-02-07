#!/usr/bin/env python3
import os, shutil, sqlite3, time

def main():
    cwd = os.getcwd()
    base = os.path.join(cwd, 'training_system')
    db = os.path.join(base, 'database', 'students.db')
    rs_dir = os.path.join(base, 'reviewed_students')
    if not os.path.exists(db):
        print('数据库不存在:', db)
        return
    ts = int(time.time())
    db_bak = db + f'.bak.{ts}'
    shutil.copy2(db, db_bak)
    print('备份数据库 ->', db_bak)
    if os.path.exists(rs_dir):
        rs_bak = rs_dir + f'.bak.{ts}'
        shutil.copytree(rs_dir, rs_bak)
        print('备份 reviewed_students ->', rs_bak)
    else:
        print('未发现 reviewed_students 目录，继续但未备份文件夹')

    conn = sqlite3.connect(db)
    cur = conn.cursor()
    rows = cur.execute("SELECT id, name, id_card, training_form_path FROM students WHERE training_form_path IS NOT NULL AND training_form_path != ''").fetchall()
    print('找到需要处理的记录数:', len(rows))

    for sid, name, id_card, tfpath in rows:
        print('\n处理 id=', sid, ' id_card=', id_card)
        if not tfpath.startswith('reviewed_students/'):
            print(' 跳过：training_form_path 不在 reviewed_students 下')
            continue
        sub = tfpath[len('reviewed_students/'):]
        old_full = os.path.join(base, 'reviewed_students', sub)
        old_folder = os.path.dirname(old_full)
        if not os.path.exists(old_folder):
            print(' 旧文件夹不存在：', old_folder)
            continue
        new_folder = os.path.join(base, 'reviewed_students', id_card)
        os.makedirs(new_folder, exist_ok=True)
        moved = False
        for fn in os.listdir(old_folder):
            src = os.path.join(old_folder, fn)
            if not os.path.isfile(src):
                continue
            name_low = fn.lower()
            ext = os.path.splitext(fn)[1] or '.jpg'
            if id_card in fn:
                new_fn = fn
            elif '体检表' in name_low:
                new_fn = f"{id_card}-体检表{ext}"
            elif '培训' in name_low:
                new_fn = f"{id_card}-培训信息登记表{ext}"
            elif '学历' in name_low or '学历证' in name_low:
                new_fn = f"{id_card}-学历证书复印件{ext}"
            elif '身份证' in name_low and '正' in name_low:
                new_fn = f"{id_card}-身份证正面{ext}"
            elif '身份证' in name_low and ('反' in name_low or '背' in name_low):
                new_fn = f"{id_card}-身份证反面{ext}"
            elif '证件' in name_low or '所持' in name_low:
                new_fn = f"{id_card}-所持证件复印件{ext}"
            else:
                new_fn = f"{id_card}-个人照片{ext}"
            dst = os.path.join(new_folder, new_fn)
            if os.path.exists(dst):
                basefn = os.path.splitext(new_fn)[0]
                i = 1
                while True:
                    candidate = f"{basefn}_{i}{ext}"
                    if not os.path.exists(os.path.join(new_folder, candidate)):
                        dst = os.path.join(new_folder, candidate)
                        break
                    i += 1
            shutil.move(src, dst)
            print(' moved:', fn, '->', os.path.relpath(dst, base))
            moved = True
        # remove old folder if empty
        try:
            if os.path.isdir(old_folder) and not os.listdir(old_folder):
                os.rmdir(old_folder)
                print(' removed empty folder', os.path.relpath(old_folder, base))
        except Exception as e:
            print(' 无法删除旧文件夹:', e)
        # update db training_form_path if docx present
        new_docx = None
        for fn in os.listdir(new_folder):
            if fn.endswith('-体检表.docx') and fn.startswith(id_card):
                new_docx = fn
                break
        if new_docx:
            new_rel = f"reviewed_students/{id_card}/{new_docx}"
            cur.execute('UPDATE students SET training_form_path = ? WHERE id = ?', (new_rel, sid))
            conn.commit()
            print(' DB updated ->', new_rel)
        else:
            print(' 未找到迁移后的体检表，DB 未更新')

    conn.close()
    print('\n迁移完成')

if __name__ == '__main__':
    main()
