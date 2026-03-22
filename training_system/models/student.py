"""
学员模型与数据库操作。

本模块定义了 students 表的结构，并提供了学员数据的完整 CRUD 操作接口。
使用 SQLite 作为数据库后端，通过上下文管理器确保连接的安全关闭和事务回滚。

数据库表结构 (students):
    - id              : 自增主键
    - name            : 姓名（必填）
    - gender          : 性别，"男"或"女"（必填）
    - education       : 文化程度（必填）
    - school          : 毕业院校（可选）
    - major           : 所学专业（可选）
    - id_card         : 身份证号，18 位（必填）
    - phone           : 手机号，11 位（必填）
    - company         : 单位名称（可选）
    - company_address : 单位地址（可选）
    - job_category    : 作业类别（必填）
    - exam_project    : 操作项目（可选）
    - project_code    : 项目代号（可选）
    - training_type   : 培训类型，special_operation 或 special_equipment
    - status          : 审核状态，unreviewed / reviewed / rejected
    - created_at      : 创建时间（自动生成）
    - photo_path      : 个人照片文件相对路径
    - diploma_path    : 学历证书文件相对路径
    - id_card_front_path   : 身份证正面照片相对路径
    - id_card_back_path    : 身份证反面照片相对路径
    - hukou_residence_path : 户口本户籍页相对路径
    - hukou_personal_path  : 户口本个人页相对路径
    - training_form_path   : 体检表/培训表文档相对路径
    - submitter_openid     : 小程序提交人 openid（用于数据归属）

索引:
    - idx_students_status_training_company : 按状态+类型+公司的复合索引（列表页筛选加速）
    - idx_students_submitter_openid        : 按提交人 openid 的索引（小程序"我的提交"加速）
    - idx_students_created_at_desc         : 按创建时间倒序索引（最新记录优先）
"""
import os
import json
import sqlite3
from contextlib import contextmanager
from flask import current_app
from utils.error_handlers import DatabaseError, NotFoundError


@contextmanager
def get_db_connection():
    """
    数据库连接上下文管理器。

    使用 with 语句管理数据库连接的生命周期：
    - 正常退出时自动提交事务 (commit)
    - 发生异常时自动回滚事务 (rollback)
    - 无论如何都会关闭连接 (close)

    使用示例:
        with get_db_connection() as conn:
            conn.execute("SELECT * FROM students")

    产出:
        sqlite3.Connection: 配置了 Row 工厂的数据库连接

    异常:
        DatabaseError: 当数据库操作失败时抛出
    """
    conn = None
    try:
        # 从 Flask 应用配置中获取数据库路径并建立连接
        conn = sqlite3.connect(current_app.config['DATABASE'])
        # 设置行工厂为 sqlite3.Row，使查询结果可以通过列名访问
        conn.row_factory = sqlite3.Row
        yield conn
        # 正常退出 with 块时提交事务
        conn.commit()
    except sqlite3.Error as e:
        # 发生数据库错误时回滚未提交的更改
        if conn:
            conn.rollback()
        current_app.logger.error(f'Database error: {str(e)}')
        raise DatabaseError(f'Database operation failed: {str(e)}')
    finally:
        # 确保连接始终被关闭，防止资源泄漏
        if conn:
            conn.close()


def _ensure_column_exists(conn, table_name, column_name, column_definition):
    """
    在列缺失时自动添加，用于轻量级模式迁移。

    当数据库表结构需要新增列时，此函数会检查列是否已存在，
    如果不存在则通过 ALTER TABLE ADD COLUMN 添加。这种方式
    比完整的数据库迁移工具更轻量，适合小型项目。

    参数:
        conn: 数据库连接对象
        table_name: 表名
        column_name: 要检查/添加的列名
        column_definition: 完整的列定义（如 "submitter_openid TEXT"）

    注意:
        SQLite 的 ALTER TABLE ADD COLUMN 有限制，不支持设置 NOT NULL
        (除非提供默认值)、不支持 UNIQUE 约束等。
    """
    # 通过 PRAGMA table_info 获取表的所有列信息
    columns = conn.execute(f'PRAGMA table_info({table_name})').fetchall()
    # 检查目标列名是否已存在于列列表中
    existed = any(str(col[1]) == column_name for col in columns)
    if not existed:
        conn.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_definition}')


def sync_config_to_json():
    """将数据库里的 training_projects 状态全量写回 job_categories.json 保持双端一致"""
    try:
        import os
        import json
        with get_db_connection() as conn:
            projects = conn.execute("SELECT * FROM training_projects ORDER BY id").fetchall()
        
        data = {
            "special_equipment": {
                "name": "特种设备", 
                "attachments": ["photo","diploma","id_card_front","id_card_back","hukou_residence","hukou_personal"],
                "job_categories": []
            },
            "special_operation": {
                "name": "特种作业", 
                "attachments": ["diploma","id_card_front","id_card_back"],
                "job_categories": []
            }
        }
        category_map = {'special_equipment': {}, 'special_operation': {}}
        
        for p in projects:
            ttype = p['training_type']
            if ttype not in data:
                continue
                
            cat_name = p['job_category']
            if cat_name not in category_map[ttype]:
                category_obj = {"name": cat_name, "exam_projects": []}
                category_map[ttype][cat_name] = category_obj
                data[ttype]["job_categories"].append(category_obj)
                
            category_map[ttype][cat_name]["exam_projects"].append({
                "name": p['exam_project'],
                "code": p['project_code'],
                "is_active": p['is_active']
            })
            
        json_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'job_categories.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        import traceback
        traceback.print_exc()

def init_db(database_path):
    """
    初始化数据库，创建必要的表和索引。

    此函数在应用启动时调用，使用 CREATE TABLE IF NOT EXISTS
    确保表结构存在但不会破坏已有数据。同时通过 _ensure_column_exists
    处理新增列的向前兼容。

    参数:
        database_path: 数据库文件绝对路径

    异常:
        DatabaseError: 数据库初始化失败时抛出
    """
    # 不使用上下文管理器，因为此时 Flask 应用上下文可能尚未初始化
    conn = sqlite3.connect(database_path)
    try:
        # 创建学员信息主表
        conn.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                gender TEXT NOT NULL,
                education TEXT NOT NULL,
                school TEXT,
                major TEXT,
                id_card TEXT NOT NULL,
                phone TEXT NOT NULL,
                company TEXT,
                company_address TEXT,
                job_category TEXT NOT NULL,
                exam_project TEXT,
                project_code TEXT,
                training_type TEXT DEFAULT 'special_operation',
                status TEXT DEFAULT 'unreviewed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                photo_path TEXT,
                diploma_path TEXT,
                id_card_front_path TEXT,
                id_card_back_path TEXT,
                hukou_residence_path TEXT,
                hukou_personal_path TEXT,
                training_form_path TEXT,
                submitter_openid TEXT,
                training_project_id INTEGER
            )
        ''')
        # 向前兼容
        _ensure_column_exists(conn, 'students', 'submitter_openid', 'submitter_openid TEXT')
        _ensure_column_exists(conn, 'students', 'training_project_id', 'training_project_id INTEGER')
        _ensure_column_exists(conn, 'students', 'hukou_residence_path', 'hukou_residence_path TEXT')

        # 创建高级字典表
        conn.execute('''
            CREATE TABLE IF NOT EXISTS training_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                training_type TEXT NOT NULL,
                job_category TEXT NOT NULL,
                exam_project TEXT NOT NULL,
                project_code TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                attachments TEXT DEFAULT '["photo","diploma","id_card_front","id_card_back","hukou_residence","hukou_personal"]'
            )
        ''')
        _ensure_column_exists(conn, 'training_projects', 'attachments', 'attachments TEXT DEFAULT \'["photo","diploma","id_card_front","id_card_back","hukou_residence","hukou_personal"]\'')

        # 同步字典表：以本地 JSON 为准，增量同步配置数据
        # 这样即使您未来直接修改 JSON 文件，重启服务后数据库能自动同步出最新选项，
        # 且改名或删除的老配置条目只会在前台隐藏，不会导致历史学员数据外键断裂。
        json_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'job_categories.json')
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 首先把所有处于“管理员通过后台手动添加的内容”以及“历史内容”软下架掉
            conn.execute("UPDATE training_projects SET is_active = 0")
            
            for training_type, type_info in data.items():
                for category in type_info.get('job_categories', []):
                    job_category = category.get('name')
                    for project in category.get('exam_projects', []):
                        exam_project = project.get('name')
                        project_code = project.get('code', '')
                        
                        # 允许在 JSON 里明确指定状态，如果未指定则默认认为是上架(1)
                        is_active = 1
                        if 'is_active' in project:
                            is_active = int(project['is_active'])
                        elif 'status' in project:
                            is_active = int(project['status'])
                        
                        # 查找这个具体的项目是否在数据库里已经存在过
                        row = conn.execute('''
                            SELECT id FROM training_projects 
                            WHERE training_type = ? AND job_category = ? AND exam_project = ? AND project_code = ?
                        ''', (training_type, job_category, exam_project, project_code)).fetchone()
                        
                        if row:
                            # 存在过，就将其更新为 JSON 里指定的上架/下架状态
                            conn.execute("UPDATE training_projects SET is_active = ? WHERE id = ?", (is_active, row[0]))
                        else:
                            # 从来没见过，作为新项目插入
                            conn.execute('''
                                INSERT INTO training_projects (training_type, job_category, exam_project, project_code, is_active)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (training_type, job_category, exam_project, project_code, is_active))

        # 创建复合索引：加速按"状态+培训类型+公司"筛选学员列表的查询
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_students_status_training_company "
            "ON students(status, training_type, company)"
        )
        # 创建索引：加速按提交人 openid 查询（小程序"我的提交"场景）
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_students_submitter_openid "
            "ON students(submitter_openid)"
        )
        # 创建倒序索引：加速按创建时间排序（最新记录优先展示）
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_students_created_at_desc "
            "ON students(created_at DESC)"
        )
        conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError(f'Failed to initialize database: {str(e)}')
    finally:
        conn.close()


def create_student(data, file_paths):
    """
    创建新的学员记录。

    将学员的个人信息和附件路径一同插入数据库。附件文件在调用此函数前
    已由 image_service 保存到文件系统中。

    参数:
        data: 包含学员个人信息的字典，必须包含以下键:
            - name, gender, education, id_card, phone, job_category
            - 可选: school, major, company, company_address, exam_project,
              project_code, training_type, submitter_openid
        file_paths: 包含附件文件相对路径的字典:
            - photo_path, diploma_path, id_card_front_path, id_card_back_path,
              hukou_residence_path, hukou_personal_path, training_form_path

    返回:
        int: 新创建的学员记录 ID（自增主键值）
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO students (
                name, gender, education, school, major, id_card, phone,
                company, company_address, job_category, exam_project, project_code,
                training_type, photo_path, diploma_path,
                id_card_front_path, id_card_back_path,
                hukou_residence_path, hukou_personal_path, training_form_path, submitter_openid,
                training_project_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data['gender'], data['education'], data.get('school', ''),
            data.get('major', ''), data['id_card'], data['phone'], data.get('company', ''),
            data.get('company_address', ''), data['job_category'], data.get('exam_project', ''),
            data.get('project_code', ''),
            data.get('training_type', 'special_operation'),
            file_paths.get('photo_path', ''), file_paths.get('diploma_path', ''),
            file_paths.get('id_card_front_path', ''), file_paths.get('id_card_back_path', ''),
            file_paths.get('hukou_residence_path', ''), file_paths.get('hukou_personal_path', ''),
            file_paths.get('training_form_path', ''), data.get('submitter_openid', ''),
            data.get('training_project_id')
        ))
        # 返回新插入记录的自增 ID
        return cursor.lastrowid


def get_students(status='unreviewed', search='', company='', training_type='', submitter_openid=''):
    """
    获取学员列表，支持多维度筛选条件。

    使用动态 SQL 拼接实现灵活的筛选查询。所有筛选条件均为可选，
    通过参数化查询（? 占位符）防止 SQL 注入。

    参数:
        status: 审核状态筛选
            - 'pending': 查询未审核和已驳回的记录（管理员待处理队列）
            - 'unreviewed' / 'reviewed' / 'rejected': 精确匹配状态
            - '': 不筛选状态
        search: 模糊搜索关键词，匹配姓名、身份证号或手机号
        company: 公司名称模糊筛选
        training_type: 培训类型精确筛选
        submitter_openid: 提交人 openid 精确筛选（小程序"我的提交"）

    返回:
        list[dict]: 学员记录字典列表，按 ID 倒序排列（最新记录在前）
    """
    with get_db_connection() as conn:
        query = """
            SELECT s.*, 
                   tp.job_category as _tp_job_category, 
                   tp.exam_project as _tp_exam_project, 
                   tp.project_code as _tp_project_code,
                   tp.training_type as _tp_training_type
            FROM students s
            LEFT JOIN training_projects tp ON s.training_project_id = tp.id
            WHERE 1=1
        """
        params = []

        # 状态筛选
        if status:
            if status == 'pending':
                # "待处理"视图：包含未审核和已驳回的记录
                query += " AND s.status IN (?, ?)"
                params.extend(['unreviewed', 'rejected'])
            else:
                query += " AND s.status = ?"
                params.append(status)

        # 培训类型筛选
        if training_type:
            query += " AND s.training_type = ?"
            params.append(training_type)

        # 关键词模糊搜索（同时匹配姓名、身份证号、手机号）
        if search:
            query += " AND (s.name LIKE ? OR s.id_card LIKE ? OR s.phone LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        # 公司名称模糊筛选
        if company:
            query += " AND s.company LIKE ?"
            params.append(f"%{company}%")

        # 提交人 openid 精确筛选
        if submitter_openid:
            query += " AND s.submitter_openid = ?"
            params.append(submitter_openid)

        # 按 ID 倒序排列，确保最新添加的记录排在前面
        query += " ORDER BY s.id DESC"

        students = conn.execute(query, params).fetchall()
        result = []
        for row in students:
            d = dict(row)
            if d.get('_tp_job_category'):
                d['job_category'] = d['_tp_job_category']
                d['exam_project'] = d['_tp_exam_project']
                d['project_code'] = d['_tp_project_code']
                d['training_type'] = d['_tp_training_type']
            for k in ['_tp_job_category', '_tp_exam_project', '_tp_project_code', '_tp_training_type']:
                d.pop(k, None)
            result.append(d)
        return result


def get_student_by_id(student_id):
    """
    根据 ID 获取单个学员记录。

    参数:
        student_id: 学员 ID（主键）

    返回:
        dict: 学员记录字典

    异常:
        NotFoundError: 当指定 ID 的学员不存在时抛出（HTTP 404）
    """
    with get_db_connection() as conn:
        query = """
            SELECT s.*, 
                   tp.job_category as _tp_job_category, 
                   tp.exam_project as _tp_exam_project, 
                   tp.project_code as _tp_project_code,
                   tp.training_type as _tp_training_type
            FROM students s
            LEFT JOIN training_projects tp ON s.training_project_id = tp.id
            WHERE s.id = ?
        """
        student = conn.execute(query, (student_id,)).fetchone()
        if not student:
            raise NotFoundError('学员不存在')
        d = dict(student)
        if d.get('_tp_job_category'):
            d['job_category'] = d['_tp_job_category']
            d['exam_project'] = d['_tp_exam_project']
            d['project_code'] = d['_tp_project_code']
            d['training_type'] = d['_tp_training_type']
        for k in ['_tp_job_category', '_tp_exam_project', '_tp_project_code', '_tp_training_type']:
            d.pop(k, None)
        return d



def update_student(student_id, updates):
    """
    更新学员记录的指定字段。

    支持部分更新（PATCH 语义），只更新传入的字段，其他字段保持不变。
    使用动态 SQL 构建 SET 子句，避免硬编码每个可更新字段。

    参数:
        student_id: 学员 ID（主键）
        updates: 要更新的字段字典，如 {'name': '张三', 'phone': '13800138000'}

    返回:
        dict: 更新后的完整学员记录

    异常:
        DatabaseError: updates 为空时抛出
        NotFoundError: 学员不存在时抛出
    """
    if not updates:
        raise DatabaseError('没有要更新的字段')

    with get_db_connection() as conn:
        # 先检查学员是否存在
        student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        if not student:
            raise NotFoundError('学员不存在')

        # 动态构建 SET 子句，如 "name = ?, phone = ?"
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        # 参数列表：先是各字段的新值，最后追加 student_id 用于 WHERE 条件
        values = list(updates.values()) + [student_id]
        conn.execute(f"UPDATE students SET {set_clause} WHERE id = ?", values)

        # 重新查询以获取更新后的完整记录
        updated = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        return dict(updated)


def delete_student(student_id):
    """
    删除学员记录。

    注意：此函数仅删除数据库记录，不会删除关联的附件文件。
    调用方需要获取返回的学员记录，然后调用 image_service.delete_student_files()
    来清理文件系统中的文件。

    参数:
        student_id: 学员 ID（主键）

    返回:
        dict: 被删除的学员记录（包含文件路径信息，供调用方清理文件）

    异常:
        NotFoundError: 学员不存在时抛出
    """
    with get_db_connection() as conn:
        # 先查询完整记录（用于返回给调用方清理文件）
        student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        if not student:
            raise NotFoundError('学员不存在')

        conn.execute('DELETE FROM students WHERE id = ?', (student_id,))
        return dict(student)


def approve_student(student_id):
    """
    审核通过学员（将状态改为 'reviewed'）。

    这是 update_student 的便捷封装，仅更新 status 字段。

    参数:
        student_id: 学员 ID（主键）

    返回:
        dict: 更新后的学员记录
    """
    return update_student(student_id, {'status': 'reviewed'})


def get_companies(status='', company_filter='', training_type=''):
    """
    获取去重后的公司名称列表，支持可选筛选条件。

    用于管理后台侧边栏的"按公司筛选"下拉列表，只返回当前条件下
    有学员数据的公司名称，避免显示空的筛选项。

    参数:
        status: 学员状态筛选（与 get_students 中的 status 参数语义一致）
        company_filter: 公司名称模糊筛选
        training_type: 培训类型筛选

    返回:
        list[str]: 按字母顺序排列的去重公司名称列表
    """
    with get_db_connection() as conn:
        # 使用 DISTINCT 去重，排除空值和空字符串
        query = """SELECT DISTINCT company FROM students
                  WHERE company IS NOT NULL AND company != ''"""
        params = []

        # 状态筛选逻辑（与 get_students 保持一致）
        if status:
            if status == 'pending':
                query += " AND status IN (?, ?)"
                params.extend(['unreviewed', 'rejected'])
            else:
                query += " AND status = ?"
                params.append(status)

        # 培训类型筛选
        if training_type:
            query += " AND training_type = ?"
            params.append(training_type)

        # 公司名称模糊筛选
        if company_filter:
            query += " AND company LIKE ?"
            params.append(f"%{company_filter}%")

        # 按公司名称字母顺序排列
        query += " ORDER BY company"

        companies = conn.execute(query, params).fetchall()
        # 提取公司名称字段值
        return [dict(c)['company'] for c in companies]
