"""
配置相关路由。

本模块提供系统配置数据的查询接口。

API 端点:
    GET /api/config/job_categories - 获取作业类别配置

配置文件位置:
    config/job_categories.json

配置数据结构:
    {
        "special_operation": {
            "name": "特种作业",
            "job_categories": [
                {
                    "name": "电工作业",
                    "exam_projects": [
                        {"name": "低压电工作业", "code": ""}
                    ]
                }
            ]
        },
        "special_equipment": { ... }
    }

此接口在 app.py 的 before_request 中间件中被列为白名单，
无需认证即可访问（前端表单下拉列表需要加载此数据）。
"""
from flask import Blueprint, jsonify, current_app, render_template, request
import json
import os

# 创建配置蓝图
config_bp = Blueprint('config', __name__)


@config_bp.route('/api/config/job_categories', methods=['GET'])
def get_job_categories():
    """
    获取作业类别配置（已迁移至数据库驱动）。

    从数据库 training_projects 表读取启用的项目，
    并动态组装回前端原本依赖的 JSON 嵌套树结构。

    返回:
        200: 作业类别配置 JSON 对象
        500: 读取失败
    """
    try:
        from models.student import get_db_connection
        
        # 基础骨架（保留培训大类的中文字段和附件依赖列表）
        config = {
            "special_operation": {
                "name": "特种作业",
                "attachments": ["diploma", "id_card_front", "id_card_back"],
                "job_categories": []
            },
            "special_equipment": {
                "name": "特种设备",
                "attachments": ["photo", "diploma", "id_card_front", "id_card_back", "hukou_residence", "hukou_personal"],
                "job_categories": []
            }
        }
        
        with get_db_connection() as conn:
            projects = conn.execute("SELECT * FROM training_projects WHERE is_active = 1 ORDER BY id").fetchall()
            
        tree = {}
        for p in projects:
            ttype = p['training_type']
            jcat = p['job_category']
            
            if ttype not in tree:
                tree[ttype] = {}
                
            if jcat not in tree[ttype]:
                tree[ttype][jcat] = []
                
            tree[ttype][jcat].append({
                "id": p['id'],  # 注入新引入的核心外键 ID
                "name": p['exam_project'],
                "code": p['project_code']
            })
            
        # 将组装好的树拼接到骨架中
        for ttype in tree:
            if ttype in config:
                for jcat_name, exam_projs in tree[ttype].items():
                    config[ttype]["job_categories"].append({
                        "name": jcat_name,
                        "exam_projects": exam_projs
                    })
                    
        return jsonify(config)
    except Exception as e:
        current_app.logger.error(f'Error loading job categories from db: {str(e)}')
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/config/storage', methods=['GET'])
def get_storage_config():
    """
    获取存储配置，供前端直接构建 COS 文件 URL 使用。

    返回:
        {
            "cos_base_url": "https://bucket.cos.region.myqcloud.com",  // COS 根地址（含前缀）
            "backend": "dual"  // 当前存储后端
        }
    """
    from services import storage_service
    import os

    backend = storage_service._get_backend()
    bucket = os.getenv('COS_BUCKET', '').strip()
    region = os.getenv('COS_REGION', '').strip()
    prefix = os.getenv('COS_KEY_PREFIX', '').strip().rstrip('/')

    cos_base_url = ''
    if bucket and region:
        base = f'https://{bucket}.cos.{region}.myqcloud.com'
        cos_base_url = f'{base}/{prefix}' if prefix else base

    return jsonify({
        'backend': backend,
        'cos_base_url': cos_base_url,  # 空字符串表示 COS 未配置，前端降级为本地路由
    })

@config_bp.route('/api/config/sts', methods=['GET'])
def get_sts_route():
    """
    颁发 COS 上传的临时通行证（STS）。
    确保小程序只往特定的临时目录进行直上传。
    """
    from services.sts_service import get_cos_sts_token
    try:
        credentials = get_cos_sts_token()
        return jsonify({
            'success': True,
            'credentials': credentials
        })
    except Exception as e:
        # 这个错会暴露给前端
        return jsonify({'error': str(e)}), 500

@config_bp.route('/api/config/wechat', methods=['GET'])
def get_wechat_config():
    """
    获取微信相关配置。

    目前主要返回用于审核结果通知的订阅消息模板 ID。
    前端小程序在提交成功后调用此接口获取需要订阅的模板配置。

    返回:
        200: 微信配置 JSON 对象
    """
    try:
        from services.wechat_service import get_wechat_template_id, get_last_broadcast_ts
        template_id = get_wechat_template_id()
        return jsonify({
            'success': True,
            'template_id': template_id,
            'last_broadcast_ts': get_last_broadcast_ts()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@config_bp.route('/admin/config', methods=['GET'])
def admin_config_page():
    return render_template('config_admin.html')

@config_bp.route('/api/config/projects/admin', methods=['GET'])
def get_admin_projects():
    try:
        from models.student import get_db_connection
        with get_db_connection() as conn:
            projects = conn.execute("SELECT * FROM training_projects ORDER BY id ASC").fetchall()
            return jsonify([dict(p) for p in projects])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@config_bp.route('/api/config/projects', methods=['POST'])
def add_project():
    try:
        from models.student import get_db_connection, sync_config_to_json
        data = request.json
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO training_projects (training_type, job_category, exam_project, project_code, is_active)
                VALUES (?, ?, ?, ?, 1)
            ''', (data['training_type'], data['job_category'], data['exam_project'], data.get('project_code', '')))
            conn.commit()
        sync_config_to_json()
        current_app.logger.info(f"管理员新增培训项目: {data['job_category']} - {data['exam_project']} ({data['training_type']})")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@config_bp.route('/api/config/projects/<int:id>', methods=['PUT'])
def edit_project(id):
    try:
        from models.student import get_db_connection, sync_config_to_json
        data = request.json
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE training_projects 
                SET training_type=?, job_category=?, exam_project=?, project_code=?
                WHERE id=?
            ''', (data['training_type'], data['job_category'], data['exam_project'], data.get('project_code', ''), id))
            
            # 同步更新现有学员记录中的冗余文本名称字段
            conn.execute('''
                UPDATE students 
                SET training_type=?, job_category=?, exam_project=?, project_code=?
                WHERE training_project_id=?
            ''', (data['training_type'], data['job_category'], data['exam_project'], data.get('project_code', ''), id))
            conn.commit()
        sync_config_to_json()
        current_app.logger.info(f"管理员修改培训项目: ID={id}, {data['job_category']} - {data['exam_project']} ({data['training_type']})")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@config_bp.route('/api/config/projects/<int:id>/toggle', methods=['POST'])
def toggle_project(id):
    try:
        from models.student import get_db_connection, sync_config_to_json
        data = request.json
        new_status = data.get('is_active', 0)
        with get_db_connection() as conn:
            conn.execute('UPDATE training_projects SET is_active = ? WHERE id = ?', (new_status, id))
            conn.commit()
        sync_config_to_json()
        current_app.logger.info(f"管理员切换培训项目状态: ID={id}, 新状态={'已上架' if new_status == 1 else '已下架'}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ======================== 附件配置 API ========================

@config_bp.route('/api/config/attachments', methods=['GET'])
def get_attachments_public():
    """
    获取各培训类型已启用的附件列表（小程序公开访问）。

    返回格式:
        {"special_equipment": ["photo", "diploma", ...], "special_operation": [...]}
    """
    try:
        from models.student import get_db_connection
        with get_db_connection() as conn:
            rows = conn.execute(
                'SELECT training_type, attachment_key FROM attachment_settings '
                'WHERE is_enabled = 1 ORDER BY training_type, sort_order'
            ).fetchall()
        result = {}
        for row in rows:
            tt = row['training_type']
            if tt not in result:
                result[tt] = []
            result[tt].append(row['attachment_key'])
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f'get_attachments_public error: {e}')
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/config/attachments/admin', methods=['GET'])
def get_attachments_admin():
    """获取全部附件及其启用状态（管理员认证）。"""
    try:
        from models.student import get_db_connection
        with get_db_connection() as conn:
            rows = conn.execute(
                'SELECT * FROM attachment_settings ORDER BY training_type, sort_order'
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@config_bp.route('/api/config/attachments/<training_type>/<attachment_key>/toggle', methods=['POST'])
def toggle_attachment(training_type, attachment_key):
    """切换指定附件的启用状态（管理员认证）。"""
    try:
        from models.student import get_db_connection
        data = request.json or {}
        new_status = int(data.get('is_enabled', 0))
        with get_db_connection() as conn:
            conn.execute(
                'UPDATE attachment_settings SET is_enabled = ? '
                'WHERE training_type = ? AND attachment_key = ?',
                (new_status, training_type, attachment_key)
            )
            conn.commit()
        current_app.logger.info(f"管理员切换附件状态: {training_type}的 {attachment_key}, 新状态={'启用' if new_status == 1 else '禁用'}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
