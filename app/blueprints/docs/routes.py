import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import (
    render_template, request, redirect, url_for, current_app,
    send_file, abort, flash, jsonify
)
from sqlalchemy import or_

from ...extensions import db
from ...models import Document, Part
from ..supplier_ws.routes import get_supplier_or_404
from . import docs_bp

# ✅ English doc types (key, label, icon, badge color)
DOC_TYPES = [
    ("drawing", "Drawing", "📐", "slate"),
    ("control_plan", "Control Plan", "🧩", "indigo"),
    ("spec", "Specification", "📄", "purple"),
    ("ppap", "PPAP", "📦", "amber"),
    ("audit", "Audit / Checklist", "✅", "emerald"),
    ("test_report", "Test Report", "🧪", "cyan"),
    ("8d", "8D Report", "🛠️", "rose"),
]

DOC_TYPE_MAP = {k: {"label": label, "icon": icon, "color": color} for k, label, icon, color in DOC_TYPES}


def _uploads_root() -> str:
    """
    Absolute uploads root folder.
    Must exist in config: current_app.config["UPLOAD_DIR"]
    Example: D:\\supplier_portal_data\\uploads
    """
    root = current_app.config.get("UPLOAD_DIR")
    if not root:
        raise RuntimeError("Missing config: UPLOAD_DIR")
    return os.path.abspath(root)


def _abs_path_from_rel(rel_path: str) -> str:
    """
    DB stores rel_path like: <supplier_code>/<doc_type>/<filename>
    Absolute path: <UPLOAD_DIR>/<rel_path>
    """
    return os.path.normpath(os.path.join(_uploads_root(), rel_path))


def _safe_join_upload_dir(supplier_code: str, doc_type: str, filename: str) -> str:
    """
    Save to: <UPLOAD_DIR>/<supplier_code>/<doc_type>/<filename>
    """
    folder = os.path.join(_uploads_root(), supplier_code, doc_type)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)


def _rel_path_from_abs(abs_path: str) -> str:
    """
    Convert absolute path -> relative path stored in DB.
    Base is UPLOAD_DIR (same drive), so no cross-drive ValueError.
    """
    rel_path = os.path.relpath(abs_path, _uploads_root())
    return rel_path.replace("\\", "/")


def _human_size(num_bytes: int) -> str:
    if num_bytes is None:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for u in units:
        if size < 1024 or u == units[-1]:
            return f"{size:.0f}{u}" if u == "B" else f"{size:.1f}{u}"
        size /= 1024
    return f"{num_bytes}B"


@docs_bp.route("/")
def list_docs(supplier_code):
    supplier = get_supplier_or_404(supplier_code)

    q = (request.args.get("q") or "").strip()
    t = (request.args.get("type") or "").strip()  # doc_type filter

    query = Document.query.filter_by(supplier_id=supplier.id)

    if t:
        query = query.filter(Document.doc_type == t)

    if q:
        query = query.outerjoin(Part, Part.id == Document.part_id).filter(
            or_(
                Document.title.ilike(f"%{q}%"),
                Document.revision.ilike(f"%{q}%"),
                Part.pn.ilike(f"%{q}%"),
            )
        )

    docs = query.order_by(Document.uploaded_at.desc()).all()

    total = len(docs)
    by_type = {}
    for d in docs:
        by_type[d.doc_type] = by_type.get(d.doc_type, 0) + 1

    enriched = []
    for d in docs:
        size_str = "-"
        try:
            abs_path = _abs_path_from_rel(d.file_path)
            if os.path.exists(abs_path):
                size_str = _human_size(os.path.getsize(abs_path))
        except Exception:
            pass

        meta = DOC_TYPE_MAP.get(d.doc_type, {"label": d.doc_type, "icon": "📎", "color": "slate"})
        enriched.append({
            "doc": d,
            "type_label": meta["label"],
            "type_icon": meta["icon"],
            "type_color": meta["color"],
            "size": size_str,
        })

    return render_template(
        "docs/list.html",
        supplier=supplier,
        docs=enriched,
        doc_types=DOC_TYPES,
        q=q,
        t=t,
        total=total,
        by_type=by_type,
    )


@docs_bp.route("/upload", methods=["GET", "POST"])
def upload_doc(supplier_code):
    supplier = get_supplier_or_404(supplier_code)
    parts = Part.query.filter_by(supplier_id=supplier.id).order_by(Part.created_at.desc()).all()

    if request.method == "POST":
        doc_type = (request.form.get("doc_type") or "drawing").strip()
        title = (request.form.get("title") or "").strip() or "Untitled"
        revision = (request.form.get("revision") or "").strip()
        status = (request.form.get("status") or "valid").strip()
        part_id_raw = (request.form.get("part_id") or "").strip()
        part_id = int(part_id_raw) if part_id_raw else None

        f = request.files.get("file")
        if not (f and f.filename):
            flash("❌ Please choose a file to upload.", "error")
            return redirect(url_for("docs.upload_doc", supplier_code=supplier.code))

        filename = secure_filename(f.filename)

        save_path = _safe_join_upload_dir(supplier.code, doc_type, filename)
        f.save(save_path)

        rel_path = _rel_path_from_abs(save_path)

        d = Document(
            supplier_id=supplier.id,
            part_id=part_id,
            doc_type=doc_type,
            title=title,
            revision=revision,
            status=status,
            file_path=rel_path,
            uploaded_at=datetime.utcnow(),
        )
        db.session.add(d)
        db.session.commit()

        flash(f"✅ '{title}' uploaded successfully.", "success")
        return redirect(url_for("docs.list_docs", supplier_code=supplier.code))

    return render_template("docs/upload.html", supplier=supplier, parts=parts, doc_types=DOC_TYPES)


@docs_bp.route("/quick-upload", methods=["POST"])
def quick_upload(supplier_code):
    """快速拖拽上传 - 支持多文件"""
    supplier = get_supplier_or_404(supplier_code)
    files = request.files.getlist("files[]")

    current_app.logger.info(f"📦 收到上传请求 - 供应商: {supplier.code}, 文件数: {len(files)}")

    if not files:
        return jsonify({"success": False, "message": "No files provided"}), 400

    uploaded_count = 0
    errors = []

    for idx, f in enumerate(files):
        if not f or not f.filename or f.filename.strip() == "":
            errors.append(f"File {idx + 1}: Empty filename")
            continue

        filename = None
        try:
            filename = secure_filename(f.filename)

            ext = os.path.splitext(filename)[1].lower()
            if ext == ".pdf":
                doc_type = "drawing"
            elif ext in [".doc", ".docx"]:
                doc_type = "spec"
            elif ext in [".xls", ".xlsx"]:
                doc_type = "control_plan"
            elif ext in [".ppt", ".pptx"]:
                doc_type = "ppap"
            elif ext in [".png", ".jpg", ".jpeg", ".gif"]:
                doc_type = "drawing"
            elif ext in [".zip", ".rar"]:
                doc_type = "ppap"
            else:
                doc_type = "drawing"

            title = os.path.splitext(filename)[0]

            save_path = _safe_join_upload_dir(supplier.code, doc_type, filename)
            f.save(save_path)

            rel_path = _rel_path_from_abs(save_path)

            d = Document(
                supplier_id=supplier.id,
                doc_type=doc_type,
                title=title,
                file_path=rel_path,
                uploaded_at=datetime.utcnow(),
            )
            db.session.add(d)
            uploaded_count += 1

        except Exception as e:
            shown_name = filename or (f.filename if f and f.filename else f"File {idx + 1}")
            errors.append(f"{shown_name}: {str(e)}")
            current_app.logger.exception("❌ Upload failed")

    if uploaded_count > 0:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": f"Database commit failed: {str(e)}"}), 500

    if errors and uploaded_count == 0:
        return jsonify({"success": False, "message": "All uploads failed", "errors": errors}), 400

    if errors:
        return jsonify({
            "success": True,
            "message": f"Uploaded {uploaded_count} file(s), {len(errors)} failed",
            "errors": errors
        })

    return jsonify({"success": True, "message": f"Successfully uploaded {uploaded_count} file(s)"})


@docs_bp.route("/send-email", methods=["POST"])
def send_email(supplier_code):
    """发送文档邮件（此处仅记录请求，实际发送逻辑你后续接入）"""
    supplier = get_supplier_or_404(supplier_code)

    data = request.get_json() or {}
    doc_id = data.get("doc_id")
    to_emails = (data.get("to") or "").strip()
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()

    if not doc_id or not to_emails or not subject:
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    doc = Document.query.filter_by(id=doc_id, supplier_id=supplier.id).first()
    if not doc:
        return jsonify({"success": False, "message": "Document not found"}), 404

    abs_path = _abs_path_from_rel(doc.file_path)
    if not os.path.exists(abs_path):
        return jsonify({"success": False, "message": "File not found"}), 404

    current_app.logger.info(f"Email request: {to_emails} - {subject} - Doc: {doc.title}")
    return jsonify({"success": True, "message": "Email sent successfully"})


@docs_bp.route("/<int:doc_id>/open")
def open_doc(supplier_code, doc_id):
    supplier = get_supplier_or_404(supplier_code)
    doc = Document.query.filter_by(id=doc_id, supplier_id=supplier.id).first_or_404()

    abs_path = _abs_path_from_rel(doc.file_path)
    if not os.path.exists(abs_path):
        abort(404)

    return send_file(abs_path, as_attachment=False)


@docs_bp.route("/<int:doc_id>/download")
def download_doc(supplier_code, doc_id):
    supplier = get_supplier_or_404(supplier_code)
    doc = Document.query.filter_by(id=doc_id, supplier_id=supplier.id).first_or_404()

    abs_path = _abs_path_from_rel(doc.file_path)
    if not os.path.exists(abs_path):
        abort(404)

    return send_file(abs_path, as_attachment=True, download_name=os.path.basename(abs_path))


@docs_bp.route("/<int:doc_id>/delete", methods=["POST"])
def delete_doc(supplier_code, doc_id):
    supplier = get_supplier_or_404(supplier_code)
    doc = Document.query.filter_by(id=doc_id, supplier_id=supplier.id).first_or_404()

    title = doc.title

    try:
        abs_path = _abs_path_from_rel(doc.file_path)
        if os.path.exists(abs_path):
            os.remove(abs_path)
    except Exception as e:
        current_app.logger.error(f"Failed to delete file: {str(e)}")

    db.session.delete(doc)
    db.session.commit()
    flash(f"✅ '{title}' deleted successfully.", "success")
    return redirect(url_for("docs.list_docs", supplier_code=supplier.code))

@docs_bp.route("/<int:doc_id>/edit", methods=["GET", "POST"])
def edit_doc(supplier_code, doc_id):
    supplier = get_supplier_or_404(supplier_code)
    doc = Document.query.filter_by(id=doc_id, supplier_id=supplier.id).first_or_404()
    parts = Part.query.filter_by(supplier_id=supplier.id).order_by(Part.created_at.desc()).all()

    if request.method == "POST":
        doc.doc_type = (request.form.get("doc_type") or doc.doc_type).strip()
        doc.title = (request.form.get("title") or "").strip() or doc.title
        doc.revision = (request.form.get("revision") or "").strip()
        doc.status = (request.form.get("status") or "valid").strip()
        part_id_raw = (request.form.get("part_id") or "").strip()
        doc.part_id = int(part_id_raw) if part_id_raw else None

        db.session.commit()
        flash(f"✅ '{doc.title}' updated successfully.", "success")
        return redirect(url_for("docs.list_docs", supplier_code=supplier.code))

    return render_template("docs/edit.html", supplier=supplier, doc=doc, parts=parts, doc_types=DOC_TYPES)