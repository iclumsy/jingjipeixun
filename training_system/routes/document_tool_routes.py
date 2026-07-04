from functools import wraps

from flask import Blueprint, jsonify, render_template, request, send_file, session

from services import document_tool_service


document_tool_bp = Blueprint("document_tool", __name__)


def _web_admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("auth_verified") is not True:
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "请先登录后台"}), 401
            return render_template("login.html", error="请先登录后台", next_path=request.path), 401
        return func(*args, **kwargs)
    return wrapper


def _success(**payload):
    return jsonify({"success": True, **payload})


def _error(message, status=400):
    return jsonify({"success": False, "message": str(message)}), status


@document_tool_bp.route("/admin/document-tools", methods=["GET"])
@_web_admin_required
def document_tools_admin_page():
    return render_template("document_tools_admin.html")


@document_tool_bp.route("/api/admin/document_tools/tasks", methods=["POST"])
@_web_admin_required
def create_document_tool_task():
    try:
        document_type = (request.form.get("document_type") or "").strip()
        task = document_tool_service.create_task(document_type, request.files)
        return _success(task=task)
    except ValueError as err:
        return _error(err, 400)
    except Exception:
        return _error("证件图片处理失败，请稍后重试", 500)


@document_tool_bp.route("/api/admin/document_tools/tasks/<task_id>", methods=["GET"])
@_web_admin_required
def get_document_tool_task(task_id):
    try:
        return _success(task=document_tool_service.get_task(task_id))
    except FileNotFoundError:
        return _error("任务不存在", 404)


@document_tool_bp.route("/api/admin/document_tools/tasks/<task_id>/analyze_points", methods=["POST"])
@_web_admin_required
def analyze_document_tool_points(task_id):
    try:
        data = request.get_json(silent=True) or {}
        return _success(points=document_tool_service.analyze_points(task_id, data.get("adjustments") or {}))
    except FileNotFoundError:
        return _error("任务不存在", 404)
    except ValueError as err:
        return _error(err, 400)


@document_tool_bp.route("/api/admin/document_tools/tasks/<task_id>/regenerate", methods=["POST"])
@_web_admin_required
def regenerate_document_tool_task(task_id):
    try:
        data = request.get_json(silent=True) or {}
        task = document_tool_service.regenerate_task(
            task_id,
            adjustments=data.get("adjustments") or {},
            points_payload=data.get("points") or {},
        )
        return _success(task=task)
    except FileNotFoundError:
        return _error("任务不存在", 404)
    except ValueError as err:
        return _error(err, 400)
    except Exception:
        return _error("重新生成失败，请稍后重试", 500)


@document_tool_bp.route("/api/admin/document_tools/tasks/<task_id>/files/<area>/<path:filename>", methods=["GET"])
@_web_admin_required
def get_document_tool_file(task_id, area, filename):
    try:
        path = document_tool_service.get_file_path(task_id, area, filename)
        return send_file(path, as_attachment=request.args.get("download") == "1")
    except FileNotFoundError:
        return _error("文件不存在", 404)
    except ValueError as err:
        return _error(err, 400)


@document_tool_bp.route("/api/admin/document_tools/tasks/<task_id>/download.zip", methods=["GET"])
@_web_admin_required
def download_document_tool_zip(task_id):
    try:
        buffer, filename = document_tool_service.build_zip(task_id)
        return send_file(
            buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename,
        )
    except FileNotFoundError:
        return _error("没有可下载的生成图片", 404)
