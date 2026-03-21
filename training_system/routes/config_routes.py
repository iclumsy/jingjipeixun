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
        from services.wechat_service import get_wechat_template_id
        template_id = get_wechat_template_id()
        return jsonify({
            'success': True,
            'template_id': template_id
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
            projects = conn.execute("SELECT * FROM training_projects ORDER BY training_type DESC, id DESC").fetchall()
            return jsonify([dict(p) for p in projects])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@config_bp.route('/api/config/projects', methods=['POST'])
def add_project():
    try:
        from models.student import get_db_connection
        data = request.json
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO training_projects (training_type, job_category, exam_project, project_code, is_active)
                VALUES (?, ?, ?, ?, 1)
            ''', (data['training_type'], data['job_category'], data['exam_project'], data.get('project_code', '')))
            conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@config_bp.route('/api/config/projects/<int:id>/toggle', methods=['POST'])
def toggle_project(id):
    try:
        from models.student import get_db_connection
        data = request.json
        with get_db_connection() as conn:
            conn.execute('UPDATE training_projects SET is_active = ? WHERE id = ?', (data['is_active'], id))
            conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
