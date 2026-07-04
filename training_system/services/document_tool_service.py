import io
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta

from flask import current_app, session
from werkzeug.utils import secure_filename

from services.material_service import (
    MaterialGenerationLogger,
    auto_crop_hukou_page,
    auto_crop_id_card,
    build_generation_report,
    crop_image_with_points,
    process_hukou,
    process_id_cards,
    read_cv_image,
    write_cv_image,
)


SESSION_ID_KEY = "document_tool_session_id"
TASK_IDS_KEY = "document_tool_task_ids"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
DOCUMENT_TYPES = {
    "id_card": {
        "label": "身份证",
        "fields": ("id_card_front", "id_card_back"),
        "point_keys": ("front_points", "back_points"),
    },
    "hukou": {
        "label": "户口本",
        "fields": ("hukou_residence", "hukou_personal"),
        "point_keys": ("home_points", "personal_points"),
    },
}


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _tool_root():
    return os.path.join(current_app.config["STUDENTS_FOLDER"], "tmp", "document_tools")


def _ensure_session_id():
    session_id = session.get(SESSION_ID_KEY)
    if not session_id:
        session_id = uuid.uuid4().hex
        session[SESSION_ID_KEY] = session_id
        session[TASK_IDS_KEY] = []
        session.modified = True
    return session_id


def _session_id():
    return session.get(SESSION_ID_KEY) or ""


def _session_task_ids():
    ids = session.get(TASK_IDS_KEY)
    if not isinstance(ids, list):
        ids = []
        session[TASK_IDS_KEY] = ids
        session.modified = True
    return ids


def _session_root(session_id=None):
    return os.path.join(_tool_root(), session_id or _session_id())


def _task_root(task_id, session_id=None):
    return os.path.join(_session_root(session_id), task_id)


def _safe_join(base, *parts):
    base_norm = os.path.abspath(base)
    target = os.path.abspath(os.path.join(base_norm, *parts))
    if target != base_norm and not target.startswith(base_norm + os.sep):
        raise ValueError("非法路径")
    return target


def _extension(filename):
    ext = os.path.splitext(filename or "")[1].lower()
    return ext if ext in ALLOWED_EXTENSIONS else ".jpg"


def _input_filename(field, uploaded_file):
    original = secure_filename(uploaded_file.filename or "")
    ext = _extension(original)
    return f"{field}{ext}"


def _task_ids_contains(task_id):
    return str(task_id or "") in {str(item) for item in _session_task_ids()}


def _manifest_path(task_id):
    return _safe_join(_task_root(task_id), "manifest.json")


def _load_manifest(task_id):
    if not _task_ids_contains(task_id):
        raise FileNotFoundError("任务不存在")
    path = _manifest_path(task_id)
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def _save_manifest(manifest):
    os.makedirs(_task_root(manifest["id"], manifest["session_id"]), exist_ok=True)
    with open(_manifest_path(manifest["id"]), "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=False, indent=2)


def _task_file_url(task_id, area, filename, download=False):
    url = f"/api/admin/document_tools/tasks/{task_id}/files/{area}/{filename}"
    return f"{url}?download=1" if download else url


def _task_zip_url(task_id):
    return f"/api/admin/document_tools/tasks/{task_id}/download.zip"


def _output_payload(task_id, filename):
    return {
        "filename": filename,
        "url": _task_file_url(task_id, "output", filename),
        "download_url": _task_file_url(task_id, "output", filename, download=True),
    }


def _input_payload(task_id, field, filename):
    return {
        "field": field,
        "filename": filename,
        "url": _task_file_url(task_id, "input", filename),
    }


def _list_outputs(task_id):
    output_dir = _safe_join(_task_root(task_id), "output")
    if not os.path.isdir(output_dir):
        return []
    return [
        _output_payload(task_id, filename)
        for filename in sorted(os.listdir(output_dir))
        if os.path.isfile(os.path.join(output_dir, filename)) and not filename.startswith(".")
    ]


def _manifest_public(manifest):
    task_id = manifest["id"]
    public = dict(manifest)
    public["inputs"] = {
        key: {k: v for k, v in value.items() if k != "path"}
        for key, value in (manifest.get("inputs") or {}).items()
    }
    public["outputs"] = _list_outputs(task_id)
    public["zip_url"] = _task_zip_url(task_id)
    return public


def cleanup_expired_sessions(max_age=None):
    root = _tool_root()
    if not os.path.isdir(root):
        return 0
    if max_age is None:
        max_age = current_app.config.get("PERMANENT_SESSION_LIFETIME") or timedelta(hours=12)
    cutoff = datetime.now().timestamp() - max_age.total_seconds()
    removed = 0
    for entry in os.scandir(root):
        if not entry.is_dir(follow_symlinks=False):
            continue
        try:
            if entry.stat(follow_symlinks=False).st_mtime < cutoff:
                shutil.rmtree(entry.path, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed


def cleanup_current_session_temp_files():
    session_id = _session_id()
    if not session_id:
        return False
    shutil.rmtree(_session_root(session_id), ignore_errors=True)
    session.pop(SESSION_ID_KEY, None)
    session.pop(TASK_IDS_KEY, None)
    session.modified = True
    return True


def _save_uploads(task_id, document_type, files):
    input_dir = _safe_join(_task_root(task_id), "input")
    os.makedirs(input_dir, exist_ok=True)
    inputs = {}
    for field in DOCUMENT_TYPES[document_type]["fields"]:
        uploaded = files.get(field)
        if not uploaded or not uploaded.filename:
            continue
        filename = _input_filename(field, uploaded)
        path = _safe_join(input_dir, filename)
        uploaded.save(path)
        inputs[field] = {
            "filename": filename,
            "path": path,
            **_input_payload(task_id, field, filename),
        }
    if not inputs:
        raise ValueError("请至少上传一张图片")
    return inputs


def _name_prefix(manifest):
    return f"临时证件-{manifest['created_at'].replace(':', '').replace('-', '')}"


def _input_path(inputs, field):
    item = inputs.get(field) or {}
    path = item.get("path") or ""
    return path if path and os.path.exists(path) else None


def _generate_outputs(manifest, adjustments=None):
    output_dir = _safe_join(_task_root(manifest["id"]), "output")
    if os.path.isdir(output_dir):
        for filename in os.listdir(output_dir):
            path = os.path.join(output_dir, filename)
            if os.path.isfile(path):
                os.remove(path)
    os.makedirs(output_dir, exist_ok=True)

    logger = MaterialGenerationLogger()
    adjustments = adjustments or {}
    inputs = manifest.get("inputs", {})
    if manifest["document_type"] == "id_card":
        result = process_id_cards(
            _input_path(inputs, "id_card_front"),
            _input_path(inputs, "id_card_back"),
            output_dir,
            _name_prefix(manifest),
            adjustments=adjustments,
            logger=logger,
        )
    elif manifest["document_type"] == "hukou":
        result = process_hukou(
            _input_path(inputs, "hukou_residence"),
            _input_path(inputs, "hukou_personal"),
            output_dir,
            _name_prefix(manifest),
            adjustments=adjustments,
            logger=logger,
        )
    else:
        raise ValueError("无效的证件类型")

    report = build_generation_report(output_dir, logger, [result])
    manifest["updated_at"] = _now_iso()
    manifest["adjustments"] = adjustments
    manifest["report"] = {
        "success": report.get("success", False),
        "log_summary": report.get("log_summary", {}),
        "log_events": report.get("log_events", []),
    }
    _save_manifest(manifest)
    if not report.get("success"):
        raise RuntimeError(result.get("error") or "生成失败")
    return _manifest_public(manifest)


def create_task(document_type, files):
    if document_type not in DOCUMENT_TYPES:
        raise ValueError("请选择身份证或户口本")
    cleanup_expired_sessions()
    session_id = _ensure_session_id()
    task_id = uuid.uuid4().hex[:16]
    os.makedirs(_task_root(task_id, session_id), exist_ok=True)
    manifest = {
        "id": task_id,
        "session_id": session_id,
        "document_type": document_type,
        "document_label": DOCUMENT_TYPES[document_type]["label"],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "inputs": {},
        "adjustments": {},
        "report": {},
    }
    manifest["inputs"] = _save_uploads(task_id, document_type, files)
    task_ids = _session_task_ids()
    task_ids.append(task_id)
    session[TASK_IDS_KEY] = task_ids[-20:]
    session.modified = True
    _save_manifest(manifest)
    return _generate_outputs(manifest)


def get_task(task_id):
    return _manifest_public(_load_manifest(task_id))


def get_file_path(task_id, area, filename):
    if area not in {"input", "output"}:
        raise FileNotFoundError("文件不存在")
    _load_manifest(task_id)
    path = _safe_join(_task_root(task_id), area, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError("文件不存在")
    return path


def build_zip(task_id):
    manifest = _load_manifest(task_id)
    files = []
    output_dir = _safe_join(_task_root(task_id), "output")
    if os.path.isdir(output_dir):
        files = [
            os.path.join(output_dir, filename)
            for filename in sorted(os.listdir(output_dir))
            if os.path.isfile(os.path.join(output_dir, filename))
        ]
    if not files:
        raise FileNotFoundError("没有可下载的生成图片")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, os.path.basename(path))
    buffer.seek(0)
    filename = f"{manifest['document_label']}-处理结果.zip"
    return buffer, filename


def _auto_points_for_path(path, document_type, adjustments, side):
    image = read_cv_image(path)
    if image is None:
        return None
    crop_mode = adjustments.get("crop_mode", "auto")
    if crop_mode == "none":
        return None
    allow_perspective = None if crop_mode == "auto" else False
    kwargs = {
        "return_meta": True,
        "allow_perspective": allow_perspective,
        "expand_level": adjustments.get("expand_level"),
        "skip_ratio_trim": adjustments.get("skip_ratio_trim", False),
    }
    if "canny_scale" in adjustments:
        kwargs["canny_scale"] = float(adjustments.get("canny_scale") or 1.0)
    if document_type == "id_card":
        _cropped, meta = auto_crop_id_card(image, **kwargs)
    else:
        _cropped, meta = auto_crop_hukou_page(image, **kwargs)
    candidate = meta.get("selected_candidate") or {}
    return candidate.get("points_orig")


def analyze_points(task_id, adjustments=None):
    manifest = _load_manifest(task_id)
    adjustments = adjustments or {}
    inputs = manifest.get("inputs", {})
    if manifest["document_type"] == "id_card":
        return {
            "front_points": _auto_points_for_path(
                _input_path(inputs, "id_card_front"),
                "id_card",
                adjustments,
                "front",
            ) if _input_path(inputs, "id_card_front") else None,
            "back_points": _auto_points_for_path(
                _input_path(inputs, "id_card_back"),
                "id_card",
                adjustments,
                "back",
            ) if _input_path(inputs, "id_card_back") else None,
        }
    return {
        "home_points": _auto_points_for_path(
            _input_path(inputs, "hukou_residence"),
            "hukou",
            adjustments,
            "home",
        ) if _input_path(inputs, "hukou_residence") else None,
        "personal_points": _auto_points_for_path(
            _input_path(inputs, "hukou_personal"),
            "hukou",
            adjustments,
            "personal",
        ) if _input_path(inputs, "hukou_personal") else None,
    }


def _crop_to_temp(path, points, crop_mode):
    if not path or not os.path.exists(path) or not points or len(points) != 4:
        return None
    if crop_mode == "none":
        return None
    image = read_cv_image(path)
    if image is None:
        return None
    mode = "rect_only" if crop_mode == "rect_only" else "perspective"
    cropped = crop_image_with_points(image, points, mode=mode)
    suffix = os.path.splitext(path)[1] or ".jpg"
    temp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir=os.path.dirname(path))
    temp.close()
    write_cv_image(temp.name, cropped)
    return temp.name


def regenerate_task(task_id, adjustments=None, points_payload=None):
    manifest = _load_manifest(task_id)
    adjustments = dict(adjustments or {})
    points_payload = points_payload or {}
    inputs = manifest.get("inputs", {})
    crop_mode = adjustments.get("crop_mode", "auto")
    temp_files = []
    original_paths = {}
    try:
        if manifest["document_type"] == "id_card":
            mapping = (
                ("id_card_front", "front_points", "front_manual_crop_applied"),
                ("id_card_back", "back_points", "back_manual_crop_applied"),
            )
        else:
            mapping = (
                ("hukou_residence", "home_points", "home_manual_crop_applied"),
                ("hukou_personal", "personal_points", "personal_manual_crop_applied"),
            )

        for field, point_key, flag_key in mapping:
            points = points_payload.get(point_key)
            if not points:
                continue
            original = _input_path(inputs, field)
            temp_path = _crop_to_temp(original, points, crop_mode)
            if temp_path:
                temp_files.append(temp_path)
                original_paths[field] = inputs[field]["path"]
                inputs[field]["path"] = temp_path
                adjustments[flag_key] = True

        manifest["inputs"] = inputs
        public = _generate_outputs(manifest, adjustments=adjustments)
        manifest["points"] = points_payload
        _save_manifest(manifest)
        return public
    finally:
        for field, path in original_paths.items():
            inputs[field]["path"] = path
        manifest["inputs"] = inputs
        _save_manifest(manifest)
        for path in temp_files:
            try:
                os.remove(path)
            except OSError:
                pass
