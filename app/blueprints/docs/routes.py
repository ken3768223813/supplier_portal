import os
from werkzeug.utils import secure_filename
from flask import render_template, request, redirect, url_for, current_app
from ...extensions import db
from ...models import Document, Part
from ..supplier_ws.routes import get_supplier_or_404
from . import docs_bp

DOC_TYPES = [
    ("drawing", "图纸"),
    ("control_plan", "控制计划"),
    ("spec", "技术规范"),
    ("ppap", "PPAP"),
    ("audit", "审核"),
    ("8d", "8D"),
]

@docs_bp.route("/")
def list_docs(supplier_code):
    supplier = get_supplier_or_404(supplier_code)
    docs = Document.query.filter_by(supplier_id=supplier.id).order_by(Document.uploaded_at.desc()).all()
    return render_template("docs/list.html", supplier=supplier, docs=docs, doc_types=DOC_TYPES)

@docs_bp.route("/upload", methods=["GET", "POST"])
def upload_doc(supplier_code):
    supplier = get_supplier_or_404(supplier_code)
    parts = Part.query.filter_by(supplier_id=supplier.id).order_by(Part.created_at.desc()).all()

    if request.method == "POST":
        doc_type = request.form.get("doc_type", "drawing")
        title = request.form.get("title", "").strip() or "Untitled"
        revision = request.form.get("revision", "").strip()
        status = request.form.get("status", "valid").strip()
        part_id_raw = request.form.get("part_id", "").strip()
        part_id = int(part_id_raw) if part_id_raw else None

        f = request.files.get("file")
        if f and f.filename:
            filename = secure_filename(f.filename)

            # 保存路径：instance/uploads/<supplier_code>/<doc_type>/
            folder = os.path.join(current_app.config["UPLOAD_DIR"], supplier.code, doc_type)
            os.makedirs(folder, exist_ok=True)

            save_path = os.path.join(folder, filename)
            f.save(save_path)

            # 数据库存相对路径（方便迁移机器）
            rel_path = os.path.relpath(save_path, os.path.join(current_app.root_path, "..", "instance"))

            d = Document(
                supplier_id=supplier.id,
                part_id=part_id,
                doc_type=doc_type,
                title=title,
                revision=revision,
                status=status,
                file_path=rel_path.replace("\\", "/"),
            )
            db.session.add(d)
            db.session.commit()

        return redirect(url_for("docs.list_docs", supplier_code=supplier.code))

    return render_template("docs/upload.html", supplier=supplier, parts=parts, doc_types=DOC_TYPES)

@docs_bp.route("/<int:doc_id>/delete", methods=["POST"])
def delete_doc(supplier_code, doc_id):
    supplier = get_supplier_or_404(supplier_code)
    doc = Document.query.filter_by(id=doc_id, supplier_id=supplier.id).first_or_404()
    db.session.delete(doc)
    db.session.commit()
    return redirect(url_for("docs.list_docs", supplier_code=supplier.code))
