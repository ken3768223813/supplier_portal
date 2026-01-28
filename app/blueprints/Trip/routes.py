from flask import render_template, request, redirect, url_for, flash, current_app, send_file, abort, Response
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from datetime import datetime
import os
import uuid

from . import trip_bp
from ...extensions import db
from ...models import BusinessTrip, TripDocument, Supplier  # ✅ 加 Supplier

import sys
import subprocess
from pathlib import Path
from flask import flash

# 文档类型定义
TRIP_DOC_TYPES = {
    "audit_plan": "审核计划",
    "audit_checklist": "审核检查表",
    "audit_report": "审核报告",
    "corrective_action": "纠正措施",
    "process_flowchart": "工艺流程图",
    "control_plan": "控制计划",
    "test_report": "测试报告",
    "meeting_minutes": "会议纪要",
    "travel_approval": "出差申请",
    "expense_report": "费用报销",
    "photos": "现场照片",
    "other": "其他文档",
}

AUDIT_TYPES = {
    "initial": "初次审核",
    "periodic": "定期审核",
    "special": "特殊审核",
    "follow_up": "跟踪审核",
}

# ✅ 简化状态（无需审批）
TRIP_STATUS = {
    "planning": "计划中",
    "ongoing": "进行中",
    "completed": "已完成",
}

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "jpg", "jpeg", "png", "zip", "rar"
}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_suppliers_for_select():
    """下拉框供应商列表（直属供应商）"""
    return Supplier.query.order_by(Supplier.code.asc()).all()


def _apply_supplier_from_form(form, current_trip=None):
    """
    支持两种方式：
    1) 选择下拉 supplier_id -> 自动回填 supplier_code/supplier_name（以 Supplier 表为准）
    2) 不选 supplier_id -> 使用手动输入 supplier_name（必填）和 supplier_code（可选）
    """
    supplier_id = (form.get("supplier_id") or "").strip()

    supplier_code = (form.get("supplier_code") or "").strip() or None
    supplier_name = (form.get("supplier_name") or "").strip()

    # ✅ 如果选择了下拉供应商，以 Supplier 表为准
    if supplier_id:
        try:
            s = Supplier.query.get(int(supplier_id))
        except ValueError:
            s = None

        if s:
            supplier_code = s.code
            supplier_name = s.name

    return supplier_code, supplier_name


@trip_bp.route("/", methods=["GET"])
def index():
    """出差管理主页 - 按供应商分组显示"""
    q = request.args.get("q", "").strip()

    # 基础查询
    query = BusinessTrip.query

    # 搜索过滤
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                BusinessTrip.trip_no.ilike(like),
                BusinessTrip.supplier_name.ilike(like),
                BusinessTrip.supplier_code.ilike(like),
                BusinessTrip.purpose.ilike(like),
                BusinessTrip.engineer.ilike(like),
            )
        )

    # ✅ 统计数据（含 planning）
    stats = {
        "total": BusinessTrip.query.count(),
        "planning": BusinessTrip.query.filter_by(status="planning").count(),
        "ongoing": BusinessTrip.query.filter_by(status="ongoing").count(),
        "completed": BusinessTrip.query.filter_by(status="completed").count(),
    }

    trips = query.order_by(
        BusinessTrip.supplier_name.asc(),
        BusinessTrip.start_date.desc()
    ).all()

    # 按供应商分组
    supplier_groups = {}
    for trip in trips:
        supplier_key = f"{trip.supplier_code or 'N/A'}_{trip.supplier_name}"
        if supplier_key not in supplier_groups:
            supplier_groups[supplier_key] = {
                "code": trip.supplier_code,
                "name": trip.supplier_name,
                "location": trip.supplier_location,
                "trips": [],
                "total_trips": 0,
                "total_docs": 0,
            }
        supplier_groups[supplier_key]["trips"].append(trip)
        supplier_groups[supplier_key]["total_trips"] += 1
        supplier_groups[supplier_key]["total_docs"] += trip.documents.count()

    return render_template(
        "trip/index.html",
        supplier_groups=supplier_groups,
        stats=stats,
        q=q,
        audit_types=AUDIT_TYPES,
        trip_status=TRIP_STATUS,
    )


@trip_bp.route("/new", methods=["GET", "POST"])
def new_trip():
    """新建出差申请"""
    suppliers = _get_suppliers_for_select()

    if request.method == "POST":
        # 生成出差编号 - 修复版本（避免重复）
        today = datetime.now()
        date_prefix = today.strftime("%Y%m%d")

        existing = BusinessTrip.query.filter(
            BusinessTrip.trip_no.like(f"TRIP-{date_prefix}-%")
        ).order_by(BusinessTrip.trip_no.desc()).first()

        if existing:
            last_no = int(existing.trip_no.split("-")[-1])
            new_no = last_no + 1
        else:
            new_no = 1

        trip_no = f"TRIP-{date_prefix}-{new_no:04d}"

        # 获取表单数据
        engineer = request.form.get("engineer", "").strip()
        supplier_code, supplier_name = _apply_supplier_from_form(request.form)
        supplier_location = request.form.get("supplier_location", "").strip() or None
        purpose = request.form.get("purpose", "").strip()
        audit_type = request.form.get("audit_type", "").strip() or None
        start_date_str = request.form.get("start_date", "").strip()
        end_date_str = request.form.get("end_date", "").strip()
        notes = request.form.get("notes", "").strip() or None

        # 表单验证
        if not engineer:
            flash("❌ 工程师姓名不能为空", "error")
            return render_template(
                "trip/form.html",
                mode="new",
                trip=None,
                documents=None,
                doc_types=TRIP_DOC_TYPES,
                audit_types=AUDIT_TYPES,
                trip_status=TRIP_STATUS,
                suppliers=suppliers,
            )

        if not supplier_name:
            flash("❌ 供应商名称不能为空", "error")
            return render_template(
                "trip/form.html",
                mode="new",
                trip=None,
                documents=None,
                doc_types=TRIP_DOC_TYPES,
                audit_types=AUDIT_TYPES,
                trip_status=TRIP_STATUS,
                suppliers=suppliers,
            )

        if not purpose:
            flash("❌ 出差目的不能为空", "error")
            return render_template(
                "trip/form.html",
                mode="new",
                trip=None,
                documents=None,
                doc_types=TRIP_DOC_TYPES,
                audit_types=AUDIT_TYPES,
                trip_status=TRIP_STATUS,
                suppliers=suppliers,
            )

        if not start_date_str or not end_date_str:
            flash("❌ 出发和返回日期不能为空", "error")
            return render_template(
                "trip/form.html",
                mode="new",
                trip=None,
                documents=None,
                doc_types=TRIP_DOC_TYPES,
                audit_types=AUDIT_TYPES,
                trip_status=TRIP_STATUS,
                suppliers=suppliers,
            )

        # 日期处理
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

            if end_date < start_date:
                flash("❌ 返回日期不能早于出发日期", "error")
                return render_template(
                    "trip/form.html",
                    mode="new",
                    trip=None,
                    documents=None,
                    doc_types=TRIP_DOC_TYPES,
                    audit_types=AUDIT_TYPES,
                    trip_status=TRIP_STATUS,
                    suppliers=suppliers,
                )

            days = (end_date - start_date).days + 1
        except ValueError:
            flash("❌ 日期格式错误", "error")
            return render_template(
                "trip/form.html",
                mode="new",
                trip=None,
                documents=None,
                doc_types=TRIP_DOC_TYPES,
                audit_types=AUDIT_TYPES,
                trip_status=TRIP_STATUS,
                suppliers=suppliers,
            )

        # 创建出差记录
        trip = BusinessTrip(
            trip_no=trip_no,
            engineer=engineer,
            supplier_code=supplier_code,
            supplier_name=supplier_name,
            supplier_location=supplier_location,
            purpose=purpose,
            audit_type=audit_type,
            start_date=start_date,
            end_date=end_date,
            days=days,
            status="planning",  # ✅ 默认计划中
            notes=notes,
        )

        db.session.add(trip)
        db.session.commit()

        flash(f"✅ 出差申请已创建：{trip_no}", "success")
        return redirect(url_for("trip.edit_trip", trip_id=trip.id))

    # GET
    return render_template(
        "trip/form.html",
        mode="new",
        trip=None,
        documents=None,
        doc_types=TRIP_DOC_TYPES,
        audit_types=AUDIT_TYPES,
        trip_status=TRIP_STATUS,
        suppliers=suppliers,  # ✅
    )


@trip_bp.route("/<int:trip_id>/edit", methods=["GET", "POST"])
def edit_trip(trip_id):
    """编辑出差申请"""
    trip = BusinessTrip.query.get_or_404(trip_id)
    suppliers = _get_suppliers_for_select()

    if request.method == "POST":
        engineer = request.form.get("engineer", "").strip()
        supplier_code, supplier_name = _apply_supplier_from_form(request.form)
        supplier_location = request.form.get("supplier_location", "").strip() or None
        purpose = request.form.get("purpose", "").strip()
        audit_type = request.form.get("audit_type", "").strip() or None
        status = request.form.get("status", "planning").strip()
        notes = request.form.get("notes", "").strip() or None

        # 验证必填字段
        if not engineer or not supplier_name or not purpose:
            flash("❌ 请填写所有必填字段", "error")
            documents = trip.documents.order_by(TripDocument.created_at.desc()).all()
            return render_template(
                "trip/form.html",
                mode="edit",
                trip=trip,
                documents=documents,
                doc_types=TRIP_DOC_TYPES,
                audit_types=AUDIT_TYPES,
                trip_status=TRIP_STATUS,
                suppliers=suppliers,
            )

        if status not in TRIP_STATUS:
            status = "planning"

        # 更新字段
        trip.engineer = engineer
        trip.supplier_code = supplier_code
        trip.supplier_name = supplier_name
        trip.supplier_location = supplier_location
        trip.purpose = purpose
        trip.audit_type = audit_type
        trip.status = status
        trip.notes = notes

        # 更新日期
        start_date_str = request.form.get("start_date", "").strip()
        end_date_str = request.form.get("end_date", "").strip()
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

                if end_date < start_date:
                    flash("❌ 返回日期不能早于出发日期", "error")
                else:
                    trip.start_date = start_date
                    trip.end_date = end_date
                    trip.days = (end_date - start_date).days + 1
            except ValueError:
                flash("❌ 日期格式错误", "error")

        db.session.commit()
        flash("✅ 出差信息已更新", "success")
        return redirect(url_for("trip.index"))

    documents = trip.documents.order_by(TripDocument.created_at.desc()).all()

    return render_template(
        "trip/form.html",
        mode="edit",
        trip=trip,
        documents=documents,
        doc_types=TRIP_DOC_TYPES,
        audit_types=AUDIT_TYPES,
        trip_status=TRIP_STATUS,
        suppliers=suppliers,  # ✅
    )


@trip_bp.route("/<int:trip_id>/delete", methods=["POST"])
def delete_trip(trip_id):
    """删除出差记录"""
    trip = BusinessTrip.query.get_or_404(trip_id)

    # 删除关联文档
    for doc in trip.documents:
        file_path = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    trip_no = trip.trip_no
    db.session.delete(trip)
    db.session.commit()

    flash(f"✅ 出差记录已删除：{trip_no}", "success")
    return redirect(url_for("trip.index"))


# ==================== 文档管理路由 ====================

@trip_bp.route("/<int:trip_id>/documents/upload", methods=["POST"])
def upload_document(trip_id):
    """上传出差文档"""
    trip = BusinessTrip.query.get_or_404(trip_id)

    if "file" not in request.files:
        flash("❌ 未选择文件", "error")
        return redirect(url_for("trip.edit_trip", trip_id=trip_id))

    file = request.files["file"]
    if not file or file.filename == "":
        flash("❌ 未选择文件", "error")
        return redirect(url_for("trip.edit_trip", trip_id=trip_id))

    if not allowed_file(file.filename):
        flash(f"❌ 不支持的文件格式。允许的格式：{', '.join(sorted(ALLOWED_EXTENSIONS))}", "error")
        return redirect(url_for("trip.edit_trip", trip_id=trip_id))

    doc_type = request.form.get("doc_type", "other")
    title = request.form.get("title", "").strip() or file.filename
    remark = request.form.get("remark", "").strip() or None

    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    if not ext:
        flash("❌ 无法识别文件扩展名", "error")
        return redirect(url_for("trip.edit_trip", trip_id=trip_id))

    stored_name = f"{uuid.uuid4().hex}.{ext}"

    trip_dir = os.path.join("trip_docs", secure_filename(trip.trip_no))
    full_dir = os.path.join(current_app.config["UPLOAD_DIR"], trip_dir)
    os.makedirs(full_dir, exist_ok=True)

    file_path = os.path.join(full_dir, stored_name)
    file.save(file_path)

    document = TripDocument(
        trip_id=trip.id,
        doc_type=doc_type,
        title=title,
        original_name=filename,
        stored_name=stored_name,
        rel_path=os.path.join(trip_dir, stored_name),
        mime=file.mimetype,
        size=os.path.getsize(file_path),
        remark=remark,
    )

    db.session.add(document)
    db.session.commit()

    flash(f"✅ 文档已上传：{title}", "success")
    return redirect(url_for("trip.edit_trip", trip_id=trip_id))


@trip_bp.route("/<int:trip_id>/documents/<int:doc_id>/view")
def view_document(trip_id, doc_id):
    """预览文档"""
    BusinessTrip.query.get_or_404(trip_id)
    doc = TripDocument.query.filter_by(id=doc_id, trip_id=trip_id).first_or_404()

    file_path = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
    if not os.path.exists(file_path):
        abort(404, "文件不存在")

    with open(file_path, "rb") as f:
        file_data = f.read()

    response = Response(file_data, mimetype=doc.mime or "application/octet-stream")
    response.headers["Content-Disposition"] = f'inline; filename="{doc.original_name}"'
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@trip_bp.route("/<int:trip_id>/documents/<int:doc_id>/download")
def download_document(trip_id, doc_id):
    """下载文档"""
    BusinessTrip.query.get_or_404(trip_id)
    doc = TripDocument.query.filter_by(id=doc_id, trip_id=trip_id).first_or_404()

    file_path = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
    if not os.path.exists(file_path):
        abort(404, "文件不存在")

    return send_file(
        file_path,
        as_attachment=True,
        download_name=doc.original_name,
        mimetype=doc.mime,
    )


@trip_bp.route("/<int:trip_id>/documents/<int:doc_id>/delete", methods=["POST"])
def delete_document(trip_id, doc_id):
    """删除文档"""
    BusinessTrip.query.get_or_404(trip_id)
    doc = TripDocument.query.filter_by(id=doc_id, trip_id=trip_id).first_or_404()

    file_path = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    title = doc.title
    db.session.delete(doc)
    db.session.commit()

    flash(f"✅ 文档已删除：{title}", "success")
    return redirect(url_for("trip.edit_trip", trip_id=trip_id))


@trip_bp.route("/<int:trip_id>/documents/panel", methods=["GET"])
def documents_panel(trip_id):
    """文档列表面板（用于模态框）"""
    trip = BusinessTrip.query.get_or_404(trip_id)
    documents = trip.documents.order_by(TripDocument.created_at.desc()).all()

    return render_template(
        "trip/_documents_panel.html",
        trip=trip,
        documents=documents,
        doc_types=TRIP_DOC_TYPES
    )



def _open_in_server_default_app(abs_path: str) -> None:
    """Open file on server machine with default application."""
    if sys.platform.startswith("win"):
        os.startfile(abs_path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", abs_path])
    else:
        # Linux
        subprocess.Popen(["xdg-open", abs_path])


@trip_bp.route("/<int:trip_id>/documents/<int:doc_id>/open_local", methods=["POST"])
def open_local_document(trip_id, doc_id):
    """服务器本机默认程序打开 Trip 文档（仅适用于你本机自用）"""
    # 校验归属
    BusinessTrip.query.get_or_404(trip_id)
    doc = TripDocument.query.filter_by(id=doc_id, trip_id=trip_id).first_or_404()

    # 拼绝对路径
    upload_root = current_app.config["UPLOAD_DIR"]
    abs_path = os.path.abspath(os.path.join(upload_root, doc.rel_path))

    # ✅ 安全：防止 rel_path 被篡改跳出 UPLOAD_DIR
    root_abs = os.path.abspath(upload_root)
    if not abs_path.startswith(root_abs + os.sep) and abs_path != root_abs:
        abort(400, "Invalid path")

    if not os.path.exists(abs_path):
        abort(404, "文件不存在")

    try:
        _open_in_server_default_app(abs_path)
        flash(f"✅ Opened on server: {doc.original_name}", "success")
    except Exception as e:
        flash(f"❌ Failed to open on server: {e}", "error")

    # 返回到你当前习惯的页面：编辑页 或 index 都可以
    return redirect(url_for("trip.index"))
