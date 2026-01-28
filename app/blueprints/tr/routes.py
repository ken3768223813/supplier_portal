from flask import render_template, request, redirect, url_for, flash, send_file, abort, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import or_
import os
import uuid

from . import tr_bp
from ...extensions import db
from ...models import TroubleReport, TRDocument, Supplier

# 8D 枚举允许值（四态）
ALLOWED_8D_STATUS = {"NOT_REQUIRED", "NOT_RECEIVED", "RECEIVED_REJECT", "RECEIVED_PASS"}

# 用于搜索：把枚举映射成中文关键词
EIGHTD_SEARCH_MAP = {
    "NOT_REQUIRED": "不要求",
    "NOT_RECEIVED": "未收到",
    "RECEIVED_REJECT": "reject",
    "RECEIVED_PASS": "pass",
}

# 文档类型选项
DOC_TYPES = {
    "quality_report": "Quality Report",
    "test_report": "Test Report",
    "8d_report": "8D Report",
    "photo": "Photos",
    "capa": "CAPA",
    "other": "Other",
}

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "jpg", "jpeg", "png", "zip", "rar"
}

# mimetype -> ext 的兜底映射
MIME_TO_EXT = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xls",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "application/zip": "zip",
    "application/x-zip-compressed": "zip",
    "application/x-rar-compressed": "rar",
}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def guess_ext(filename: str, mimetype: str) -> str:
    ext = ""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[1].lower().strip()

    if not ext:
        mt = (mimetype or "").lower().strip()
        ext = MIME_TO_EXT.get(mt, "")

    return ext


@tr_bp.route("/", methods=["GET"])
def index():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = TroubleReport.query

    if q:
        like = f"%{q}%"
        extra_8d_status = []
        q_lower = q.lower()
        for k, v in EIGHTD_SEARCH_MAP.items():
            if v in q_lower:
                extra_8d_status.append(k)

        query = query.filter(
            or_(
                TroubleReport.tr_no.ilike(like),
                TroubleReport.supplier_name.ilike(like),
                TroubleReport.part_number.ilike(like),
                TroubleReport.part_name.ilike(like),
                TroubleReport.issue_description.ilike(like),
                TroubleReport.severity.ilike(like),
                TroubleReport.eight_d.ilike(like),
                TroubleReport.eight_d_status.ilike(like),
                TroubleReport.eight_d_status.in_(extra_8d_status) if extra_8d_status else False,
                TroubleReport.status.ilike(like),
                TroubleReport.remark.ilike(like),
            )
        )

    query = query.order_by(TroubleReport.created_at.desc(), TroubleReport.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    trs = pagination.items

    return render_template(
        "tr/index.html",
        trs=trs,
        pagination=pagination,
        q=q,
        per_page=per_page,
    )


@tr_bp.route("/new", methods=["GET", "POST"])
def new_tr():
    if request.method == "POST":
        tr_no = (request.form.get("tr_no") or "").strip()
        supplier_name = (request.form.get("supplier_name") or "").strip()
        part_number = (request.form.get("part_number") or "").strip() or None
        part_name = (request.form.get("part_name") or "").strip() or None
        issue_description = (request.form.get("issue_description") or "").strip()
        severity = (request.form.get("severity") or "").strip() or None

        eight_d = (request.form.get("eight_d") or "").strip() or None
        eight_d_status = (request.form.get("eight_d_status") or "NOT_REQUIRED").strip()
        if eight_d_status not in ALLOWED_8D_STATUS:
            eight_d_status = "NOT_REQUIRED"

        status = (request.form.get("status") or "Open").strip() or "Open"
        remark = (request.form.get("remark") or "").strip() or None

        if not tr_no:
            flash("TR No. cannot be empty", "error")
            suppliers = Supplier.query.order_by(Supplier.code).all()  # ← 改为 code
            return render_template("tr/form.html", mode="new", tr=None, suppliers=suppliers)

        if not supplier_name:
            flash("Supplier Name cannot be empty", "error")
            suppliers = Supplier.query.order_by(Supplier.code).all()  # ← 改为 code
            return render_template("tr/form.html", mode="new", tr=None, suppliers=suppliers)

        if not issue_description:
            flash("Issue Description cannot be empty", "error")
            suppliers = Supplier.query.order_by(Supplier.code).all()  # ← 改为 code
            return render_template("tr/form.html", mode="new", tr=None, suppliers=suppliers)

        exists = TroubleReport.query.filter_by(tr_no=tr_no).first()
        if exists:
            flash(f"TR No. already exists: {tr_no}", "error")
            suppliers = Supplier.query.order_by(Supplier.code).all()  # ← 改为 code
            return render_template("tr/form.html", mode="new", tr=None, suppliers=suppliers)

        tr = TroubleReport(
            tr_no=tr_no,
            supplier_code="N/A",
            supplier_name=supplier_name,
            part_number=part_number,
            part_name=part_name,
            issue_description=issue_description,
            severity=severity,
            eight_d=eight_d,
            eight_d_status=eight_d_status,
            status=status,
            remark=remark,
        )
        db.session.add(tr)
        db.session.commit()

        flash("✅ TR created successfully", "success")
        return redirect(url_for("tr.index"))

    # GET 请求：获取供应商列表
    suppliers = Supplier.query.order_by(Supplier.code).all()  # ← 改为 code
    return render_template("tr/form.html", mode="new", tr=None, suppliers=suppliers)


@tr_bp.route("/<int:tr_id>/edit", methods=["GET", "POST"])
def edit_tr(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)

    if request.method == "POST":
        tr_no = (request.form.get("tr_no") or "").strip()
        supplier_name = (request.form.get("supplier_name") or "").strip()
        part_number = (request.form.get("part_number") or "").strip() or None
        part_name = (request.form.get("part_name") or "").strip() or None
        issue_description = (request.form.get("issue_description") or "").strip()
        severity = (request.form.get("severity") or "").strip() or None

        eight_d = (request.form.get("eight_d") or "").strip() or None
        eight_d_status = (request.form.get("eight_d_status") or "NOT_REQUIRED").strip()
        if eight_d_status not in ALLOWED_8D_STATUS:
            eight_d_status = "NOT_REQUIRED"

        status = (request.form.get("status") or "Open").strip() or "Open"
        remark = (request.form.get("remark") or "").strip() or None

        if not tr_no:
            flash("TR No. cannot be empty", "error")
            documents = tr.documents.order_by(TRDocument.created_at.desc()).all()
            suppliers = Supplier.query.order_by(Supplier.code).all()  # ← 改为 code
            return render_template("tr/form.html", mode="edit", tr=tr, documents=documents, doc_types=DOC_TYPES, suppliers=suppliers)

        if not supplier_name:
            flash("Supplier Name cannot be empty", "error")
            documents = tr.documents.order_by(TRDocument.created_at.desc()).all()
            suppliers = Supplier.query.order_by(Supplier.code).all()  # ← 改为 code
            return render_template("tr/form.html", mode="edit", tr=tr, documents=documents, doc_types=DOC_TYPES, suppliers=suppliers)

        if not issue_description:
            flash("Issue Description cannot be empty", "error")
            documents = tr.documents.order_by(TRDocument.created_at.desc()).all()
            suppliers = Supplier.query.order_by(Supplier.code).all()  # ← 改为 code
            return render_template("tr/form.html", mode="edit", tr=tr, documents=documents, doc_types=DOC_TYPES, suppliers=suppliers)

        if tr_no != tr.tr_no:
            exists = TroubleReport.query.filter_by(tr_no=tr_no).first()
            if exists:
                flash(f"TR No. already exists: {tr_no}", "error")
                documents = tr.documents.order_by(TRDocument.created_at.desc()).all()
                suppliers = Supplier.query.order_by(Supplier.code).all()  # ← 改为 code
                return render_template("tr/form.html", mode="edit", tr=tr, documents=documents, doc_types=DOC_TYPES, suppliers=suppliers)

        tr.tr_no = tr_no
        tr.supplier_name = supplier_name
        tr.part_number = part_number
        tr.part_name = part_name
        tr.issue_description = issue_description
        tr.severity = severity
        tr.eight_d = eight_d
        tr.eight_d_status = eight_d_status
        tr.status = status
        tr.remark = remark

        db.session.commit()
        flash("✅ TR updated successfully", "success")
        return redirect(url_for("tr.index"))

    # GET 请求：获取供应商列表和文档
    documents = tr.documents.order_by(TRDocument.created_at.desc()).all()
    suppliers = Supplier.query.order_by(Supplier.code).all()  # ← 改为 code
    return render_template("tr/form.html", mode="edit", tr=tr, documents=documents, doc_types=DOC_TYPES, suppliers=suppliers)


@tr_bp.route("/<int:tr_id>/delete", methods=["POST"])
def delete_tr(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)

    for doc in tr.documents:
        file_path = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    db.session.delete(tr)
    db.session.commit()
    flash("✅ TR deleted successfully", "success")
    return redirect(url_for("tr.index"))


# ==================== 文档管理路由 ====================

@tr_bp.route("/<int:tr_id>/documents/upload", methods=["POST"])
def upload_document(tr_id):
    """上传 TR 文档"""
    tr = TroubleReport.query.get_or_404(tr_id)

    if "file" not in request.files:
        flash("❌ No file selected", "error")
        return redirect(url_for("tr.edit_tr", tr_id=tr_id))

    file = request.files["file"]
    if not file or file.filename == "":
        flash("❌ No file selected", "error")
        return redirect(url_for("tr.edit_tr", tr_id=tr_id))

    raw_name = (file.filename or "").strip()

    if not allowed_file(raw_name):
        flash(f"❌ Unsupported file format. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}", "error")
        return redirect(url_for("tr.edit_tr", tr_id=tr_id))

    doc_type = request.form.get("doc_type", "other")
    title = (request.form.get("title") or "").strip()
    remark = (request.form.get("remark") or "").strip() or None

    if not title:
        title = raw_name

    ext = guess_ext(raw_name, file.mimetype)

    if not ext:
        flash("❌ Cannot recognize file extension. Please use standard filename (e.g., .xlsx/.pdf/.docx)", "error")
        return redirect(url_for("tr.edit_tr", tr_id=tr_id))

    stored_name = f"{uuid.uuid4().hex}.{ext}"
    original_name_to_store = raw_name or secure_filename(raw_name) or stored_name

    tr_dir = os.path.join("tr_docs", secure_filename(tr.tr_no))
    full_dir = os.path.join(current_app.config["UPLOAD_DIR"], tr_dir)
    os.makedirs(full_dir, exist_ok=True)

    file_path = os.path.join(full_dir, stored_name)
    file.save(file_path)

    file_size = os.path.getsize(file_path)
    mime_type = file.mimetype

    rel_path = os.path.join(tr_dir, stored_name)

    document = TRDocument(
        tr_id=tr.id,
        doc_type=doc_type,
        title=title,
        original_name=original_name_to_store,
        stored_name=stored_name,
        rel_path=rel_path,
        mime=mime_type,
        size=file_size,
        remark=remark,
    )
    db.session.add(document)
    db.session.commit()

    flash(f"✅ Document uploaded: {title}", "success")
    return redirect(url_for("tr.edit_tr", tr_id=tr_id))


@tr_bp.route("/<int:tr_id>/documents/<int:doc_id>/view")
def view_document(tr_id, doc_id):
    TroubleReport.query.get_or_404(tr_id)
    doc = TRDocument.query.filter_by(id=doc_id, tr_id=tr_id).first_or_404()

    file_path = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
    if not os.path.exists(file_path):
        abort(404, "File not found")

    from flask import make_response

    response = make_response(send_file(
        file_path,
        mimetype=doc.mime or 'application/octet-stream',
    ))

    response.headers['Content-Disposition'] = f'inline; filename="{doc.original_name}"'
    response.headers['X-Content-Type-Options'] = 'nosniff'

    return response


@tr_bp.route("/<int:tr_id>/documents/<int:doc_id>/download")
def download_document(tr_id, doc_id):
    TroubleReport.query.get_or_404(tr_id)
    doc = TRDocument.query.filter_by(id=doc_id, tr_id=tr_id).first_or_404()

    file_path = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
    if not os.path.exists(file_path):
        abort(404, "File not found")

    return send_file(
        file_path,
        as_attachment=True,
        download_name=doc.original_name,
        mimetype=doc.mime,
    )


@tr_bp.route("/<int:tr_id>/documents/<int:doc_id>/delete", methods=["POST"])
def delete_document(tr_id, doc_id):
    TroubleReport.query.get_or_404(tr_id)
    doc = TRDocument.query.filter_by(id=doc_id, tr_id=tr_id).first_or_404()

    file_path = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    db.session.delete(doc)
    db.session.commit()

    flash(f"✅ Document deleted: {doc.title}", "success")
    return redirect(url_for("tr.edit_tr", tr_id=tr_id))


@tr_bp.route("/<int:tr_id>/documents/panel", methods=["GET"])
def documents_panel(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    documents = tr.documents.order_by(TRDocument.created_at.desc()).all()

    return render_template(
        "tr/_documents_panel.html",
        tr=tr,
        documents=documents,
        doc_types=DOC_TYPES
    )