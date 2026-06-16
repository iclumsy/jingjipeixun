#!/bin/bash

# stats_recent_passed.sh
# 统计近一周（或指定天数）考试通过的学员信息

# 设置颜色变量
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # 重置颜色

# 获取天数参数，默认为 7 天
DAYS=${1:-7}

# 自动定位到脚本所在目录，防止路径错乱
cd "$(dirname "$0")"

DB_PATH="database/students.db"

if [ ! -f "$DB_PATH" ]; then
    echo -e "${RED}❌ 错误：在当前目录下未找到数据库文件 $DB_PATH${NC}"
    echo -e "请将此脚本放置在项目 training_system 目录下运行。"
    exit 1
fi

echo -e "${BLUE}=== 开始统计近 ${DAYS} 天内理论考试通过的学员信息 ===${NC}"

python3 -c "
import sqlite3
import csv
import sys
from datetime import datetime, timedelta

db_path = '$DB_PATH'
days = int('$DAYS')

# 计算起始时间
start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 查询操作日志和学员表联查
    sql = '''
        SELECT 
            s.id,
            s.name,
            s.phone,
            s.id_card,
            s.company,
            s.exam_project,
            o.created_at AS pass_time,
            o.actor_name AS operator
        FROM operation_logs o
        JOIN students s ON o.student_id = s.id
        WHERE o.action = 'student_exam_passed'
          AND o.created_at >= ?
        ORDER BY o.created_at DESC
    '''
    
    cursor.execute(sql, (start_date,))
    rows = cursor.fetchall()
    
    if not rows:
        print('\033[0;33m⚠️ 提示：近 {} 天内没有通过理论考试的学员。\033[0m'.format(days))
        sys.exit(0)
        
    # 打印终端表头
    print('\033[0;36m{:<6} | {:<8} | {:<12} | {:<19} | {:<18} | {:<20} | {:<10}\033[0m'.format(
        'ID', '姓名', '手机号', '身份证号', '考试项目', '通过时间', '操作人'
    ))
    print('-' * 110)
    
    csv_rows = []
    for r in rows:
        id_card = r['id_card'] or '-'
        
        # 终端排版展示
        print('{:<6} | {:<8} | {:<12} | {:<19} | {:<18} | {:<20} | {:<10}'.format(
            str(r['id']),
            str(r['name'])[:8],
            str(r['phone']),
            str(id_card),
            str(r['exam_project'])[:16],
            str(r['pass_time']),
            str(r['operator'])[:10]
        ))
        
        csv_rows.append({
            '学员ID': r['id'],
            '姓名': r['name'],
            '手机号': r['phone'],
            '身份证号': r['id_card'],
            '所属公司': r['company'] or '',
            '考试项目': r['exam_project'] or '',
            '考试通过时间': r['pass_time'],
            '操作管理员': r['operator'] or ''
        })
        
    print('-' * 110)
    print('\033[0;32m✅ 统计完成！近 {} 天内共通过学员: {} 人。\033[0m'.format(days, len(rows)))
    
    # 自动保存一份 CSV
    csv_file = 'passed_students_recent_{}days.csv'.format(days)
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['学员ID', '姓名', '手机号', '身份证号', '所属公司', '考试项目', '考试通过时间', '操作管理员'])
        writer.writeheader()
        writer.writerows(csv_rows)
    print('\033[0;34mℹ️ 详细数据已自动导出至当前目录下的：{}\033[0m'.format(csv_file))

except Exception as e:
    print('\033[0;31m❌ 查询出错: {}\033[0m'.format(str(e)))
    sys.exit(1)
"
