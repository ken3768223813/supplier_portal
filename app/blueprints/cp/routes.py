from datetime import date, datetime
import csv
import io
import json
import os
import uuid

from flask import (
    abort, current_app, flash, jsonify, make_response, redirect,
    render_template, request, send_file, url_for,
)
from sqlalchemy import func
from werkzeug.utils import secure_filename

from app.control_plan_helper import (
    PARSER_VERSION, assess_quality, extract_control_plan, sha256_file,
)
from app.extensions import db
from app.models import (
    ControlCharacteristic, ControlPlan, ControlPlanVersion,
    Part, ProcessStep, Supplier,
)
from . import cp_bp


PROCESS_TYPES = [
    ("ced", "电泳 CED"),
    ("coating", "喷涂 Coating"),
    ("plating", "电镀 Plating"),
    ("casting", "铸造 Casting"),
    ("hpdc", "压铸 HPDC"),
    ("stamping", "冲压 Stamping"),
    ("injection", "注塑 Injection"),
    ("machining", "机加工 Machining"),
    ("welding", "焊接 Welding"),
    ("assembly", "装配 Assembly"),
    ("forging", "锻造 Forging"),
    ("extrusion", "挤压 Extrusion"),
    ("other", "其他 Other"),
]
PROCESS_LABELS = dict(PROCESS_TYPES)
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "xlsm", "ppt", "pptx"}
OFFICE_EXTS = {"doc", "docx", "xls", "xlsx", "xlsm", "ppt", "pptx"}


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _loads(value, default):
    try:
        parsed = json.loads(value) if value else default
        return parsed if parsed is not None else default
    except (TypeError, ValueError):
        return default


def _safe_path(rel_path):
    upload_root = os.path.abspath(current_app.config["UPLOAD_DIR"])
    file_path = os.path.abspath(os.path.join(upload_root, (rel_path or "").replace("/", os.sep)))
    if os.path.commonpath([upload_root, file_path]) != upload_root:
        abort(404)
    return file_path


def _latest_version(cp):
    return cp.versions.order_by(ControlPlanVersion.version_no.desc()).first()


def _selected_version(cp, version_id=None):
    if version_id:
        version = ControlPlanVersion.query.filter_by(id=version_id, cp_id=cp.id).first_or_404()
        return version
    if cp.published_version_id:
        published = ControlPlanVersion.query.filter_by(
            id=cp.published_version_id, cp_id=cp.id
        ).first()
        if published:
            return published
    return _latest_version(cp)


def _version_data(version):
    if not version:
        return {"metadata": {}, "steps": [], "quality_score": 0, "quality_issues": []}
    data = _loads(version.structured_json, {})
    data.setdefault("metadata", _loads(version.metadata_json, {}))
    data.setdefault("steps", [])
    data.setdefault("quality_score", version.quality_score or 0)
    data.setdefault("quality_issues", _loads(version.quality_issues, []))
    return data


def _store_upload(file, cp, version_no):
    extension = file.filename.rsplit(".", 1)[1].lower()
    stored_name = f"{uuid.uuid4().hex}.{extension}"
    rel_dir = os.path.join(
        "control_plans",
        secure_filename(cp.supplier.code),
        secure_filename(cp.cp_no),
        f"v{version_no:03d}",
    )
    full_dir = os.path.join(current_app.config["UPLOAD_DIR"], rel_dir)
    os.makedirs(full_dir, exist_ok=True)
    file_path = os.path.join(full_dir, stored_name)
    file.save(file_path)
    return (
        file_path,
        os.path.join(rel_dir, stored_name).replace("\\", "/"),
        stored_name,
    )


def _apply_extraction(cp, version, file_path, force_ai=False):
    version.extract_status = "processing"
    version.extraction_error = None
    db.session.flush()
    try:
        data = extract_control_plan(
            file_path, force_ai=force_ai, logger=current_app.logger
        )
        version.structured_json = json.dumps(data, ensure_ascii=False)
        version.metadata_json = json.dumps(data.get("metadata", {}), ensure_ascii=False)
        version.quality_issues = json.dumps(
            data.get("quality_issues", []), ensure_ascii=False
        )
        version.source_sheet = data.get("source_sheet")
        version.source_template = data.get("source_template")
        version.parser_version = data.get("parser_version") or PARSER_VERSION
        version.ai_model = data.get("ai_model")
        version.confidence = data.get("confidence")
        version.quality_score = data.get("quality_score")
        version.extract_status = "review"
        version.status = "review"
        cp.structure_status = "review"
        cp.quality_score = version.quality_score
        cp.source_template = version.source_template
        return data
    except Exception as exc:
        current_app.logger.exception("[CP] extraction failed for %s", file_path)
        version.extract_status = "failed"
        version.status = "review"
        version.extraction_error = str(exc)
        cp.structure_status = "failed"
        return None


def _append_version(cp, file, revision):
    latest_no = db.session.query(func.max(ControlPlanVersion.version_no)).filter(
        ControlPlanVersion.cp_id == cp.id
    ).scalar() or 0
    version_no = latest_no + 1
    file_path, rel_path, stored_name = _store_upload(file, cp, version_no)
    version = ControlPlanVersion(
        cp_id=cp.id,
        version_no=version_no,
        revision=revision,
        status="review",
        extract_status="pending",
        original_name=file.filename,
        stored_name=stored_name,
        rel_path=rel_path,
        mime=file.mimetype,
        size=os.path.getsize(file_path),
        file_sha256=sha256_file(file_path),
    )
    db.session.add(version)

    cp.original_name = file.filename
    cp.stored_name = stored_name
    cp.rel_path = rel_path
    cp.mime = file.mimetype
    cp.size = version.size
    cp.revision = revision
    cp.updated_at = datetime.utcnow()
    cp.structure_status = "processing"
    db.session.flush()
    data = _apply_extraction(cp, version, file_path)
    return version, data


@cp_bp.route("/")
def index():
    process_type = request.args.get("process_type", "")
    supplier_id = request.args.get("supplier_id", "")
    q = request.args.get("q", "").strip()
    query = ControlPlan.query.join(Part).join(
        Supplier, ControlPlan.supplier_id == Supplier.id
    ).filter(ControlPlan.status != "obsolete")

    if process_type:
        query = query.filter(ControlPlan.process_type == process_type)
    if supplier_id:
        query = query.filter(ControlPlan.supplier_id == int(supplier_id))
    if q:
        like = f"%{q}%"
        query = query.filter(
            Part.pn.ilike(like)
            | Part.description.ilike(like)
            | Supplier.name.ilike(like)
            | Supplier.chinese_name.ilike(like)
            | Supplier.code.ilike(like)
            | ControlPlan.cp_no.ilike(like)
        )

    cps = query.order_by(ControlPlan.updated_at.desc()).all()
    latest_versions = {cp.id: _latest_version(cp) for cp in cps}
    suppliers = Supplier.query.order_by(Supplier.code).all()
    return render_template(
        "cp/index.html",
        cps=cps,
        latest_versions=latest_versions,
        suppliers=suppliers,
        process_types=PROCESS_TYPES,
        process_labels=PROCESS_LABELS,
        selected_type=process_type,
        selected_supplier=supplier_id,
        q=q,
    )


@cp_bp.route("/upload", methods=["POST"])
def upload():
    supplier_id = request.form.get("supplier_id", type=int)
    part_id = request.form.get("part_id", type=int)
    process_type = (request.form.get("process_type") or "other").strip()
    revision = (request.form.get("revision") or "A0").strip()
    notes = (request.form.get("notes") or "").strip()
    audit_date = request.form.get("audit_date") or None
    file = request.files.get("file")

    if not supplier_id or not part_id:
        flash("请选择供应商和零件", "error")
        return redirect(url_for("cp.index"))
    if not file or not file.filename:
        flash("请选择要上传的控制计划文件", "error")
        return redirect(url_for("cp.index"))
    if not _allowed(file.filename):
        flash("仅支持 PDF / Office 文档", "error")
        return redirect(url_for("cp.index"))

    supplier = Supplier.query.get_or_404(supplier_id)
    part = Part.query.get_or_404(part_id)
    cp = ControlPlan.query.filter_by(
        supplier_id=supplier_id, part_id=part_id, process_type=process_type
    ).first()
    if not cp:
        cp_no = f"CP-{supplier.code}-{part.pn}-{process_type}".upper()[:50]
        cp = ControlPlan(
            supplier_id=supplier_id,
            part_id=part_id,
            cp_no=cp_no,
            process_type=process_type,
            revision=revision,
            status="draft",
            structure_status="pending",
        )
        db.session.add(cp)
        db.session.flush()

    cp.notes = notes
    if audit_date:
        cp.audit_date = date.fromisoformat(audit_date)
    version, data = _append_version(cp, file, revision)
    db.session.commit()

    if data and data.get("steps"):
        char_count = sum(
            len(step.get("characteristics", [])) for step in data["steps"]
        )
        flash(
            f"版本 V{version.version_no} 已保存，识别到 "
            f"{len(data['steps'])} 道工序、{char_count} 条控制特性，请审核后发布。",
            "success",
        )
    else:
        flash("原文件和版本已保存，但结构化内容需要人工检查。", "warning")
    return redirect(url_for("cp.detail", cp_id=cp.id, tab="review", version_id=version.id))


@cp_bp.route("/<int:cp_id>")
def detail(cp_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    requested_version = request.args.get("version_id", type=int)
    versions = cp.versions.order_by(ControlPlanVersion.version_no.desc()).all()
    requested_tab = request.args.get("tab")
    latest = versions[0] if versions else None
    if requested_version:
        version = _selected_version(cp, requested_version)
    elif requested_tab == "review":
        version = latest
    elif not requested_tab and latest and latest.status == "review":
        version = latest
    else:
        version = _selected_version(cp)
    data = _version_data(version)
    characteristic_count = sum(
        len(step.get("characteristics", [])) for step in data.get("steps", [])
    )
    critical_count = sum(
        issue.get("count", 0)
        for issue in data.get("quality_issues", [])
        if issue.get("severity") == "critical"
    )
    review_step_index = request.args.get("step", 0, type=int)
    if data.get("steps"):
        review_step_index = max(0, min(review_step_index, len(data["steps"]) - 1))
        review_step = data["steps"][review_step_index]
    else:
        review_step_index = 0
        review_step = None
    tab = requested_tab
    if tab not in {"standard", "review", "original", "history"}:
        tab = "review" if version and version.status == "review" else "standard"
    return render_template(
        "cp/detail.html",
        cp=cp,
        version=version,
        versions=versions,
        data=data,
        characteristic_count=characteristic_count,
        critical_count=critical_count,
        review_step_index=review_step_index,
        review_step=review_step,
        tab=tab,
        process_labels=PROCESS_LABELS,
    )


@cp_bp.route("/<int:cp_id>/versions/<int:version_id>/save", methods=["POST"])
def save_review(cp_id, version_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    version = ControlPlanVersion.query.filter_by(
        id=version_id, cp_id=cp.id
    ).first_or_404()
    data = _version_data(version)
    metadata = data.setdefault("metadata", {})
    for key in (
        "control_plan_number", "part_number", "part_name", "organization",
        "compiled_date", "revised_date",
    ):
        metadata[key] = (request.form.get(f"meta_{key}") or "").strip()

    step_index = request.form.get("step_index", 0, type=int)
    if 0 <= step_index < len(data.get("steps", [])):
        step = data["steps"][step_index]
        prefix = f"s{step_index}_"
        step["process_code"] = (request.form.get(prefix + "process_code") or "").strip()
        step["process_name"] = (
            request.form.get(prefix + "process_name") or "Unspecified process"
        ).strip()
        step["machine"] = (request.form.get(prefix + "machine") or "").strip()
        step["notes"] = (request.form.get(prefix + "notes") or "").strip()
        step["is_key_process"] = request.form.get(prefix + "is_key_process") == "1"
        for char_index, characteristic in enumerate(step.get("characteristics", [])):
            char_prefix = f"s{step_index}c{char_index}_"
            for key in (
                "char_code", "char_name", "char_type", "special_class",
                "spec_value", "measurement_method", "sample_size", "frequency",
                "inspector", "control_method", "reaction_plan",
            ):
                characteristic[key] = (
                    request.form.get(char_prefix + key) or ""
                ).strip()
            characteristic["is_key_char"] = (
                request.form.get(char_prefix + "is_key_char") == "1"
            )

    score, issues = assess_quality(data)
    data["quality_score"] = score
    data["quality_issues"] = issues
    version.structured_json = json.dumps(data, ensure_ascii=False)
    version.metadata_json = json.dumps(metadata, ensure_ascii=False)
    version.quality_score = score
    version.quality_issues = json.dumps(issues, ensure_ascii=False)
    version.status = "review"
    version.extract_status = "review"
    cp.quality_score = score
    cp.structure_status = "review"
    cp.updated_at = datetime.utcnow()
    db.session.commit()
    flash("结构化控制计划已保存，原始附件没有改变。", "success")
    return redirect(url_for(
        "cp.detail", cp_id=cp.id, tab="review", version_id=version.id, step=step_index
    ))


@cp_bp.route("/<int:cp_id>/versions/<int:version_id>/publish", methods=["POST"])
def publish(cp_id, version_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    version = ControlPlanVersion.query.filter_by(
        id=version_id, cp_id=cp.id
    ).first_or_404()
    data = _version_data(version)
    if not data.get("steps"):
        flash("没有可发布的结构化工序，请先重新识别或人工补充。", "error")
        return redirect(url_for("cp.detail", cp_id=cp.id, tab="review", version_id=version.id))

    for old_step in cp.steps.all():
        db.session.delete(old_step)
    db.session.flush()

    for step_data in data["steps"]:
        step = ProcessStep(
            cp_id=cp.id,
            seq=step_data.get("seq") or 10,
            process_name=step_data.get("process_name") or "Unspecified process",
            process_code=step_data.get("process_code"),
            machine=step_data.get("machine"),
            is_key_process=bool(step_data.get("is_key_process")),
            notes=step_data.get("notes"),
            source_sheet=step_data.get("source_sheet"),
            source_row=step_data.get("source_row"),
        )
        db.session.add(step)
        db.session.flush()
        for item in step_data.get("characteristics", []):
            db.session.add(ControlCharacteristic(
                step_id=step.id,
                char_name=item.get("char_name") or "Control characteristic",
                char_type=item.get("char_type") or "product",
                char_code=item.get("char_code"),
                special_class=item.get("special_class"),
                spec_value=item.get("spec_value"),
                spec_unit=item.get("spec_unit"),
                tolerance=item.get("tolerance"),
                measurement_method=item.get("measurement_method"),
                control_method=item.get("control_method"),
                sample_size=item.get("sample_size"),
                frequency=item.get("frequency"),
                inspector=item.get("inspector"),
                reaction_plan=item.get("reaction_plan"),
                is_key_char=bool(item.get("is_key_char")),
                source_sheet=item.get("source_sheet"),
                source_row=item.get("source_row"),
                confidence=item.get("confidence"),
            ))

    ControlPlanVersion.query.filter(
        ControlPlanVersion.cp_id == cp.id,
        ControlPlanVersion.status == "published",
        ControlPlanVersion.id != version.id,
    ).update({"status": "superseded"}, synchronize_session=False)
    version.status = "published"
    version.extract_status = "complete"
    version.published_at = datetime.utcnow()
    cp.published_version_id = version.id
    cp.status = "active"
    cp.structure_status = "published"
    cp.revision = version.revision or cp.revision
    cp.quality_score = version.quality_score
    cp.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f"版本 V{version.version_no} 已发布为当前控制计划。", "success")
    return redirect(url_for("cp.detail", cp_id=cp.id, tab="standard"))


@cp_bp.route("/<int:cp_id>/versions/<int:version_id>/reanalyze", methods=["POST"])
def reanalyze(cp_id, version_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    version = ControlPlanVersion.query.filter_by(
        id=version_id, cp_id=cp.id
    ).first_or_404()
    file_path = _safe_path(version.rel_path)
    if not os.path.exists(file_path):
        abort(404)
    data = _apply_extraction(cp, version, file_path, force_ai=True)
    db.session.commit()
    if data and data.get("steps"):
        flash("AI 已重新分析列结构，请检查提取结果。", "success")
    else:
        flash("AI 未能建立可靠映射，原文件仍已完整保留。", "warning")
    return redirect(url_for("cp.detail", cp_id=cp.id, tab="review", version_id=version.id))


@cp_bp.route("/<int:cp_id>/view")
def view(cp_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    version = _selected_version(cp, request.args.get("version_id", type=int))
    rel_path = version.rel_path if version else cp.rel_path
    original_name = version.original_name if version else cp.original_name
    mime = version.mime if version else cp.mime
    if not rel_path:
        abort(404)
    file_path = _safe_path(rel_path)
    if not os.path.exists(file_path):
        abort(404)
    extension = (
        original_name.rsplit(".", 1)[-1].lower()
        if original_name and "." in original_name else ""
    )
    if extension in OFFICE_EXTS:
        try:
            from app.blueprints.tr.routes import PREVIEW_CACHE_DIR, _convert_to_pdf
            cache_dir = os.path.join(current_app.config["UPLOAD_DIR"], PREVIEW_CACHE_DIR)
            pdf_path = _convert_to_pdf(file_path, cache_dir, current_app.logger)
            if pdf_path:
                response = make_response(send_file(pdf_path, mimetype="application/pdf"))
                response.headers["Content-Disposition"] = (
                    f'inline; filename="{cp.cp_no}.pdf"'
                )
                return response
        except Exception:
            current_app.logger.exception("[CP] preview conversion failed")
        return send_file(
            file_path, as_attachment=True, download_name=original_name, mimetype=mime
        )
    response = make_response(send_file(file_path, mimetype=mime or "application/octet-stream"))
    response.headers["Content-Disposition"] = f'inline; filename="{original_name}"'
    return response


@cp_bp.route("/<int:cp_id>/download")
def download(cp_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    version = _selected_version(cp, request.args.get("version_id", type=int))
    rel_path = version.rel_path if version else cp.rel_path
    original_name = version.original_name if version else cp.original_name
    mime = version.mime if version else cp.mime
    if not rel_path:
        abort(404)
    file_path = _safe_path(rel_path)
    if not os.path.exists(file_path):
        abort(404)
    return send_file(
        file_path,
        as_attachment=True,
        download_name=original_name or f"{cp.cp_no}.pdf",
        mimetype=mime,
    )


@cp_bp.route("/<int:cp_id>/export.csv")
def export_csv(cp_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    version = _selected_version(cp, request.args.get("version_id", type=int))
    data = _version_data(version)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Process No.", "Process Name", "Equipment", "Characteristic No.",
        "Characteristic", "Type", "Special Class", "Specification / Tolerance",
        "Measurement Method", "Sample Size", "Frequency", "Inspector",
        "Control Method", "Reaction Plan", "Source",
    ])
    for step in data.get("steps", []):
        characteristics = step.get("characteristics") or [{}]
        for item in characteristics:
            writer.writerow([
                step.get("process_code", ""),
                step.get("process_name", ""),
                step.get("machine", ""),
                item.get("char_code", ""),
                item.get("char_name", ""),
                item.get("char_type", ""),
                item.get("special_class", ""),
                item.get("spec_value", ""),
                item.get("measurement_method", ""),
                item.get("sample_size", ""),
                item.get("frequency", ""),
                item.get("inspector", ""),
                item.get("control_method", ""),
                item.get("reaction_plan", ""),
                f"{item.get('source_sheet', '')}!{item.get('source_row', '')}",
            ])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{secure_filename(cp.cp_no)}-standard.csv"'
    )
    return response


@cp_bp.route("/<int:cp_id>/edit", methods=["POST"])
def edit(cp_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    new_process = (request.form.get("process_type") or cp.process_type).strip()
    if new_process != cp.process_type:
        clash = ControlPlan.query.filter(
            ControlPlan.supplier_id == cp.supplier_id,
            ControlPlan.part_id == cp.part_id,
            ControlPlan.process_type == new_process,
            ControlPlan.id != cp.id,
            ControlPlan.status != "obsolete",
        ).first()
        if clash:
            flash("该零件已有相同工艺的控制计划。", "error")
            return redirect(url_for("cp.index"))
        cp.process_type = new_process

    revision = (request.form.get("revision") or cp.revision or "A0").strip()
    cp.revision = revision
    cp.notes = (request.form.get("notes") or "").strip()
    audit_date = request.form.get("audit_date")
    if audit_date:
        cp.audit_date = date.fromisoformat(audit_date)

    file = request.files.get("file")
    if file and file.filename:
        if not _allowed(file.filename):
            flash("仅支持 PDF / Office 文档", "error")
            return redirect(url_for("cp.index"))
        version, _ = _append_version(cp, file, revision)
        db.session.commit()
        flash(f"已新增版本 V{version.version_no}，旧版本仍完整保留。", "success")
        return redirect(url_for("cp.detail", cp_id=cp.id, tab="review", version_id=version.id))

    cp.updated_at = datetime.utcnow()
    db.session.commit()
    flash("控制计划信息已更新。", "success")
    return redirect(url_for("cp.detail", cp_id=cp.id))


@cp_bp.route("/<int:cp_id>/delete", methods=["POST"])
def delete(cp_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    cp.status = "obsolete"
    cp.structure_status = "archived"
    cp.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f"控制计划 {cp.cp_no} 已归档，历史文件未删除。", "info")
    return redirect(url_for("cp.index"))


@cp_bp.route("/api/parts/<int:supplier_id>")
def api_parts(supplier_id):
    parts = Part.query.filter_by(supplier_id=supplier_id).order_by(Part.pn).all()
    return jsonify([
        {"id": part.id, "pn": part.pn, "description": part.description or ""}
        for part in parts
    ])
