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
from flask import Blueprint, jsonify, current_app
import json
import os

# 创建配置蓝图
config_bp = Blueprint('config', __name__)


@config_bp.route('/api/config/job_categories', methods=['GET'])
def get_job_categories():
    """
    获取作业类别配置。

    从 JSON 配置文件中读取所有培训类型及其包含的作业类别和操作项目。
    前端和小程序均使用此接口动态生成下拉选项。

    返回:
        200: 作业类别配置 JSON 对象
        500: 配置文件读取失败
    """
    try:
        # 构建配置文件绝对路径（相对于 routes 目录的上级目录）
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'job_categories.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        current_app.logger.error(f'Error loading job categories config: {str(e)}')
        return jsonify({'error': str(e)}), 500
