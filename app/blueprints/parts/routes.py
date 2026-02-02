import os
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, current_app, send_file
from werkzeug.utils import secure_filename

from ...extensions import db
from ...models import Supplier, Part, Drawing
from ..supplier_ws.routes import get_supplier_or_404
from . import parts_bp

from flask import send_file, make_response


@parts_bp.route("/")
def list_parts(supplier_code):
    supplier = get_supplier_or_404(supplier_code)
    parts = Part.query.filter_by(supplier_id=supplier.id).order_by(Part.created_at.desc()).all()

    # 先做最基础统计（后续你接上 Document 后再改成真实值）
    stats = {
        "total_parts": len(parts),
        "with_drawing": 0,
        "with_cp": 0,
        "need_update": 0,
    }

    q = request.args.get("q", "").strip()

    query = Part.query.filter_by(supplier_id=supplier.id)

    if q:
        query = query.filter(
            (Part.pn.ilike(f"%{q}%")) |
            (Part.description.ilike(f"%{q}%")) |
            (Part.project.ilike(f"%{q}%"))
        )

    parts = query.order_by(Part.created_at.desc()).all()

    return render_template("parts/list.html", supplier=supplier, parts=parts, stats=stats, q=q)


@parts_bp.route("/new", methods=["GET", "POST"])
def new_part(supplier_code):
    supplier = get_supplier_or_404(supplier_code)
    if request.method == "POST":
        pn = request.form.get("pn", "").strip()
        description = request.form.get("description", "").strip()
        project = request.form.get("project", "").strip()
        remark = request.form.get("remark", "").strip()

        if not pn:
            flash("❌ Part number is required.", "error")
            return render_template("parts/form.html", supplier=supplier)

        # 检查是否已存在相同的 Part Number（同一供应商下）
        existing_part = Part.query.filter_by(
            supplier_id=supplier.id,
            pn=pn
        ).first()

        if existing_part:
            flash(f"❌ Part number '{pn}' already exists for this supplier.", "error")
            return render_template("parts/form.html",
                                   supplier=supplier,
                                   form_data={
                                       'pn': pn,
                                       'description': description,
                                       'project': project,
                                       'remark': remark
                                   })

        p = Part(supplier_id=supplier.id, pn=pn, description=description, project=project, remark=remark)
        db.session.add(p)
        db.session.commit()
        flash(f"✅ Part '{pn}' created successfully.", "success")
        return redirect(url_for("parts.list_parts", supplier_code=supplier.code))

    return render_template("parts/form.html", supplier=supplier)


@parts_bp.route("/<int:part_id>/delete", methods=["POST"])
def delete_part(supplier_code, part_id):
    supplier = get_supplier_or_404(supplier_code)
    part = Part.query.filter_by(id=part_id, supplier_id=supplier.id).first_or_404()

    pn = part.pn
    db.session.delete(part)
    db.session.commit()
    flash(f"✅ Part '{pn}' deleted successfully.", "success")
    return redirect(url_for("parts.list_parts", supplier_code=supplier.code))


@parts_bp.route("/<int:part_id>/edit", methods=["GET", "POST"])
def edit_part(supplier_code, part_id):
    supplier = get_supplier_or_404(supplier_code)
    part = Part.query.filter_by(id=part_id, supplier_id=supplier.id).first_or_404()

    if request.method == "POST":
        new_pn = request.form.get("pn", "").strip()
        description = request.form.get("description", "").strip() or None
        project = request.form.get("project", "").strip() or None

        if not new_pn:
            flash("❌ Part number is required.", "error")
            return redirect(url_for("parts.edit_part", supplier_code=supplier_code, part_id=part_id))

        # 如果修改了 Part Number，检查是否与其他零部件重复
        if new_pn != part.pn:
            existing_part = Part.query.filter_by(
                supplier_id=supplier.id,
                pn=new_pn
            ).filter(Part.id != part_id).first()

            if existing_part:
                flash(f"❌ Part number '{new_pn}' already exists for this supplier.", "error")
                return redirect(url_for("parts.edit_part", supplier_code=supplier_code, part_id=part_id))

        part.pn = new_pn
        part.description = description
        part.project = project
        db.session.commit()
        flash("✅ Part updated successfully.", "success")
        return redirect(url_for("parts.list_parts", supplier_code=supplier_code))

    drawings = (Drawing.query
                .filter_by(supplier_id=supplier.id, part_id=part.id)
                .order_by(Drawing.created_at.desc())
                .all())

    return render_template("parts/form.html",
                           supplier=supplier,
                           part=part,
                           mode="edit",
                           drawings=drawings)


def _drawing_upload_dir(supplier_code: str, pn: str) -> str:
    base = current_app.config["UPLOAD_DIR"]
    return os.path.join(base, "suppliers", supplier_code, "parts", pn, "drawings")


@parts_bp.route("/<int:part_id>/drawings", methods=["GET"])
def drawings_panel(supplier_code, part_id):
    """给 modal 用：返回某个零部件的图纸版本列表（HTML片段）"""
    supplier = get_supplier_or_404(supplier_code)
    part = Part.query.filter_by(id=part_id, supplier_id=supplier.id).first_or_404()

    drawings = (Drawing.query
                .filter_by(part_id=part.id, supplier_id=supplier.id)
                .order_by(Drawing.created_at.desc())
                .all())

    return render_template("parts/_drawings_panel.html", supplier=supplier, part=part, drawings=drawings)


@parts_bp.route("/<int:part_id>/drawings/upload", methods=["POST"])
def upload_drawing(supplier_code, part_id):
    supplier = get_supplier_or_404(supplier_code)
    part = Part.query.filter_by(id=part_id, supplier_id=supplier.id).first_or_404()

    f = request.files.get("file")
    revision = (request.form.get("revision") or "A0").strip()
    title = (request.form.get("title") or "").strip() or None
    remark = (request.form.get("remark") or "").strip() or None
    eff = (request.form.get("effective_date") or "").strip()

    if not f or f.filename.strip() == "":
        flash("❌ Please select a file to upload.", "error")
        return redirect(url_for("parts.edit_part", supplier_code=supplier.code, part_id=part.id))

    # 简单限制：只允许 pdf / 图片（你可扩展）
    filename = secure_filename(f.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".dwg", ".dxf", ".step", ".stp"]:
        flash("❌ Only PDF, PNG, JPG, WEBP, DWG, DXF, STEP formats are supported.", "error")
        return redirect(url_for("parts.edit_part", supplier_code=supplier.code, part_id=part.id))

    up_dir = _drawing_upload_dir(supplier.code, part.pn)
    os.makedirs(up_dir, exist_ok=True)

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    stored_name = f"{stamp}_{revision}{ext}"
    abs_path = os.path.join(up_dir, stored_name)
    f.save(abs_path)

    rel_path = os.path.relpath(abs_path, current_app.config["UPLOAD_DIR"]).replace("\\", "/")

    d = Drawing(
        supplier_id=supplier.id,
        part_id=part.id,
        revision=revision,
        title=title,
        remark=remark,
        effective_date=datetime.strptime(eff, "%Y-%m-%d").date() if eff else None,
        original_name=filename,
        stored_name=stored_name,
        rel_path=rel_path,
        mime=f.mimetype,
        size=os.path.getsize(abs_path),
    )
    db.session.add(d)
    db.session.commit()

    flash(f"✅ Drawing revision '{revision}' uploaded successfully.", "success")
    return redirect(url_for("parts.edit_part", supplier_code=supplier.code, part_id=part.id))


@parts_bp.route("/drawings/<int:drawing_id>/delete", methods=["POST"])
def delete_drawing(supplier_code, drawing_id):
    supplier = get_supplier_or_404(supplier_code)
    d = Drawing.query.filter_by(id=drawing_id, supplier_id=supplier.id).first_or_404()

    # 删除文件
    abs_path = os.path.join(current_app.config["UPLOAD_DIR"], d.rel_path.replace("/", os.sep))
    if os.path.exists(abs_path):
        os.remove(abs_path)

    part_id = d.part_id
    revision = d.revision
    db.session.delete(d)
    db.session.commit()

    flash(f"✅ Drawing revision '{revision}' deleted successfully.", "success")
    return redirect(url_for("parts.edit_part", supplier_code=supplier.code, part_id=part_id))


@parts_bp.route("/drawings/<int:drawing_id>/view", methods=["GET"])
def view_drawing(supplier_code, drawing_id):
    """modal 预览用：浏览器 inline 打开，不下载"""
    supplier = get_supplier_or_404(supplier_code)
    d = Drawing.query.filter_by(
        id=drawing_id,
        supplier_id=supplier.id
    ).first_or_404()

    abs_path = os.path.join(
        current_app.config["UPLOAD_DIR"],
        d.rel_path.replace("/", os.sep)
    )

    resp = make_response(send_file(
        abs_path,
        mimetype=d.mime or "application/pdf"
    ))
    resp.headers["Content-Disposition"] = "inline"
    return resp