#!/usr/bin/env python3
"""
一次性脚本：将已开卡的学员标记为 card_activated=1
执行方式：在服务器上 cd 到项目根目录后运行
    python fix_card_activated.py

执行前请确认 DB_PATH 指向正确的数据库文件。
"""
import sqlite3
from datetime import datetime

DB_PATH = 'database/students.db'  # 根据实际路径修改

# ========== 在此填写已开卡学员的 ID ==========
# 可以用身份证号查找：先运行
#   sqlite3 instance/students.db "SELECT id, name, id_card FROM students WHERE training_type='special_equipment' AND status='reviewed';"
# 确认后填入下方列表
STUDENT_IDS = []  # 例如 [12, 15]
# =============================================

def main():
    if not STUDENT_IDS:
        # 如果没有填 ID，则交互式展示所有特种设备已审核学员供选择
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, name, id_card, phone, card_activated "
            "FROM students "
            "WHERE training_type='special_equipment' AND status='reviewed' "
            "ORDER BY id DESC"
        ).fetchall()
        conn.close()

        if not rows:
            print("没有找到符合条件的特种设备已审核学员。")
            return

        print("\n特种设备已审核学员列表：")
        print(f"{'ID':>5}  {'姓名':<8}  {'身份证号':<20}  {'手机号':<13}  {'已开卡':>6}")
        print("-" * 65)
        for r in rows:
            activated = '✅ 是' if r['card_activated'] else '❌ 否'
            print(f"{r['id']:>5}  {r['name']:<8}  {r['id_card']:<20}  {r['phone']:<13}  {activated:>6}")

        print("\n请将需要标记的学员 ID 填入脚本顶部 STUDENT_IDS 列表后重新运行。")
        print("例如: STUDENT_IDS = [12, 15]")
        return

    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat()

    for sid in STUDENT_IDS:
        row = conn.execute("SELECT id, name, card_activated FROM students WHERE id = ?", (sid,)).fetchone()
        if not row:
            print(f"[跳过] ID={sid} 学员不存在")
            continue
        conn.execute(
            "UPDATE students SET card_activated = 1, card_activated_at = ? WHERE id = ?",
            (now, sid)
        )
        print(f"[更新] ID={sid} 姓名={row[1]} → card_activated=1")

    conn.commit()
    conn.close()
    print(f"\n完成，共更新 {len(STUDENT_IDS)} 条记录。")

if __name__ == '__main__':
    main()
