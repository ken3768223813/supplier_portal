import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import (
    render_template, request, redirect, url_for, current_app,
    send_file, abort, flash
)
from sqlalchemy import or_

from ...extensions import db
from ...models import Document, Part
from ..supplier_ws.routes import get_supplier_or_404
from . import docs_bp


# ✅ English doc types (key, label, icon, badge color)
DOC_TYPES = [
    ("drawing",       "Drawing",            "📐", "slate"),
    ("control_plan",  "Control Plan",       "🧩", "indigo"),
    ("spec",          "Specification",      "📄", "purple"),
    ("ppap",          "PPAP",               "📦", "amber"),
    ("audit",         "Audit / Checklist",  "✅", "emerald"),
    ("test_report",   "Test Report",        "🧪", "cyan"),
    ("8d",            "8D Report",          "🛠️", "rose"),
]

DOC_TYPE_MAP = {k: {"label": label, "icon": icon, "color": color} for k, label, icon, color in DOC_TYPES}


def _instance_abs_path_from_rel(rel_path: str) -> str:
    """
    rel_path stored like: uploads/<supplier_code>/<doc_type>/<filename>
    Absolute should be: <project>/instance/<rel_path>
    """
    instance_root = os.path.join(current_app.root_path, "..", "instance")
    return os.path.normpath(os.path.join(instance_root, rel_path))


def _safe_join_upload_dir(supplier_code: str, doc_type: str, filename: str) -> str:
    # instance/uploads/<supplier_code>/<doc_type>/<filename>
    folder = os.path.join(current_app.config["UPLOAD_DIR"], supplier_code, doc_type)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)


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
        # Search in title/revision + part pn
        query = query.outerjoin(Part, Part.id == Document.part_id).filter(
            or_(
                Document.title.ilike(f"%{q}%"),
                Document.revision.ilike(f"%{q}%"),
                Part.pn.ilike(f"%{q}%"),
            )
        )

    docs = query.order_by(Document.uploaded_at.desc()).all()

    # Simple stats
    total = len(docs)
    by_type = {}
    for d in docs:
        by_type[d.doc_type] = by_type.get(d.doc_type, 0) + 1

    # enrich display fields (size, badge info)
    enriched = []
    for d in docs:
        size_str = "-"
        try:
            abs_path = _instance_abs_path_from_rel(d.file_path)
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
            flash("Please choose a file to upload.", "warning")
            return redirect(url_for("docs.upload_doc", supplier_code=supplier.code))

        filename = secure_filename(f.filename)

        save_path = _safe_join_upload_dir(supplier.code, doc_type, filename)
        f.save(save_path)

        # Store relative path under instance/
        rel_path = os.path.relpath(save_path, os.path.join(current_app.root_path, "..", "instance"))
        rel_path = rel_path.replace("\\", "/")

        d = Document(
            supplier_id=supplier.id,
            part_id=part_id,
            doc_type=doc_type,
            title=title,
            revision=revision,
            status=status,
            file_path=rel_path,
            uploaded_at=datetime.utcnow(),  # if your model already has default, this won't hurt
        )
        db.session.add(d)
        db.session.commit()

        flash("Uploaded successfully.", "success")
        return redirect(url_for("docs.list_docs", supplier_code=supplier.code))

    return render_template("docs/upload.html", supplier=supplier, parts=parts, doc_types=DOC_TYPES)


@docs_bp.route("/<int:doc_id>/open")
def open_doc(supplier_code, doc_id):
    supplier = get_supplier_or_404(supplier_code)
    doc = Document.query.filter_by(id=doc_id, supplier_id=supplier.id).first_or_404()

    abs_path = _instance_abs_path_from_rel(doc.file_path)
    if not os.path.exists(abs_path):
        abort(404)

    # inline open in browser if possible
    return send_file(abs_path, as_attachment=False)


@docs_bp.route("/<int:doc_id>/download")
def download_doc(supplier_code, doc_id):
    supplier = get_supplier_or_404(supplier_code)
    doc = Document.query.filter_by(id=doc_id, supplier_id=supplier.id).first_or_404()

    abs_path = _instance_abs_path_from_rel(doc.file_path)
    if not os.path.exists(abs_path):
        abort(404)

    return send_file(abs_path, as_attachment=True)


@docs_bp.route("/<int:doc_id>/delete", methods=["POST"])
def delete_doc(supplier_code, doc_id):
    supplier = get_supplier_or_404(supplier_code)
    doc = Document.query.filter_by(id=doc_id, supplier_id=supplier.id).first_or_404()

    # (optional) also delete the file on disk
    try:
        abs_path = _instance_abs_path_from_rel(doc.file_path)
        if os.path.exists(abs_path):
            os.remove(abs_path)
    except Exception:
        pass

    db.session.delete(doc)
    db.session.commit()
    flash("Deleted.", "success")
    return redirect(url_for("docs.list_docs", supplier_code=supplier.code))
