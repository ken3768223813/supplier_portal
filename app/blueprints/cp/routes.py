from flask import (
    render_template, request, redirect, url_for, flash, jsonify,
    send_file, abort, current_app, make_response
)
from werkzeug.utils import secure_filename
import os
import uuid

from app.extensions import db
from app.models import ControlPlan, Supplier, Part
from datetime import date, datetime
from . import cp_bp


PROCESS_TYPES = [
    ('ced',      '电泳 CED'),
    ('coating',  '喷涂 Coating'),
    ('plating',  '电镀 Plating'),
    ('casting',   '铸造 Casting'),
    ('hpdc',      '压铸 HPDC'),
    ('stamping',  '冲压 Stamping'),
    ('injection', '注塑 Injection'),
    ('machining', '机加工 Machining'),
    ('welding',   '焊接 Welding'),
    ('assembly',  '装配 Assembly'),
    ('forging',   '锻造 Forging'),
    ('extrusion', '挤压 Extrusion'),
    ('other',     '其他 Other'),
]
PROCESS_LABELS = dict(PROCESS_TYPES)

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx"}
OFFICE_EXTS = {"doc", "docx", "xls", "xlsx", "ppt", "pptx"}


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ─────────────────────────────────────────────
# 列表页（带搜索 / 筛选）
# ─────────────────────────────────────────────
@cp_bp.route('/')
def index():
    process_type = request.args.get('process_type', '')
    supplier_id  = request.args.get('supplier_id', '')
    q            = request.args.get('q', '').strip()

    query = ControlPlan.query.join(Part).join(Supplier, ControlPlan.supplier_id == Supplier.id)

    if process_type:
        query = query.filter(ControlPlan.process_type == process_type)
    if supplier_id:
        query = query.filter(ControlPlan.supplier_id == int(supplier_id))
    if q:
        like = f'%{q}%'
        query = query.filter(
            Part.pn.ilike(like) |
            Part.description.ilike(like) |
            Supplier.name.ilike(like) |
            Supplier.chinese_name.ilike(like) |
            Supplier.code.ilike(like) |
            ControlPlan.cp_no.ilike(like)
        )

    cps       = query.order_by(ControlPlan.updated_at.desc()).all()
    suppliers = Supplier.query.order_by(Supplier.code).all()

    return render_template('cp/index.html',
                           cps=cps,
                           suppliers=suppliers,
                           process_types=PROCESS_TYPES,
                           process_labels=PROCESS_LABELS,
                           selected_type=process_type,
                           selected_supplier=supplier_id,
                           q=q)


# ─────────────────────────────────────────────
# 上传控制计划（新建 / 替换）
# ─────────────────────────────────────────────
@cp_bp.route('/upload', methods=['POST'])
def upload():
    supplier_id  = request.form.get('supplier_id', type=int)
    part_id      = request.form.get('part_id', type=int)
    process_type = (request.form.get('process_type') or 'other').strip()
    revision     = (request.form.get('revision') or 'A0').strip()
    notes        = (request.form.get('notes') or '').strip()
    audit_date   = request.form.get('audit_date') or None

    if not supplier_id or not part_id:
        flash('请选择供应商和零件', 'error')
        return redirect(url_for('cp.index'))

    file = request.files.get('file')
    if not file or file.filename == '':
        flash('请选择要上传的控制计划文件', 'error')
        return redirect(url_for('cp.index'))
    if not _allowed(file.filename):
        flash('仅支持 PDF / Office 文档', 'error')
        return redirect(url_for('cp.index'))

    supplier = Supplier.query.get_or_404(supplier_id)
    part     = Part.query.get_or_404(part_id)

    # 保存文件
    ext = file.filename.rsplit('.', 1)[1].lower()
    stored_name = f'{uuid.uuid4().hex}.{ext}'
    rel_dir = os.path.join('control_plans', secure_filename(supplier.code))
    full_dir = os.path.join(current_app.config['UPLOAD_DIR'], rel_dir)
    os.makedirs(full_dir, exist_ok=True)
    file_path = os.path.join(full_dir, stored_name)
    file.save(file_path)
    rel_path = os.path.join(rel_dir, stored_name)

    # 已存在同供应商+零件+工艺 → 替换文件，否则新建
    cp = ControlPlan.query.filter_by(
        supplier_id=supplier_id, part_id=part_id, process_type=process_type
    ).first()

    if cp:
        # 删除旧文件
        if cp.rel_path:
            old = os.path.join(current_app.config['UPLOAD_DIR'], cp.rel_path)
            if os.path.exists(old):
                try:
                    os.remove(old)
                except OSError:
                    pass
        cp.original_name = file.filename
        cp.stored_name   = stored_name
        cp.rel_path      = rel_path
        cp.mime          = file.mimetype
        cp.size          = os.path.getsize(file_path)
        cp.revision      = revision
        cp.notes         = notes
        cp.audit_date    = date.fromisoformat(audit_date) if audit_date else cp.audit_date
        cp.updated_at    = datetime.utcnow()
        flash(f'已更新 {part.pn} 的控制计划', 'success')
    else:
        cp_no = f'CP-{supplier.code}-{part.pn}-{process_type}'.upper()[:50]
        cp = ControlPlan(
            supplier_id=supplier_id, part_id=part_id, cp_no=cp_no,
            process_type=process_type, revision=revision, status='active',
            notes=notes,
            audit_date=date.fromisoformat(audit_date) if audit_date else None,
            original_name=file.filename, stored_name=stored_name,
            rel_path=rel_path, mime=file.mimetype, size=os.path.getsize(file_path),
        )
        db.session.add(cp)
        flash(f'已上传 {part.pn} 的控制计划', 'success')

    db.session.commit()
    return redirect(url_for('cp.index'))


# ─────────────────────────────────────────────
# 在线预览（PDF 内联；Office 转 PDF）
# ─────────────────────────────────────────────
@cp_bp.route('/<int:cp_id>/view')
def view(cp_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    if not cp.rel_path:
        abort(404)
    file_path = os.path.join(current_app.config['UPLOAD_DIR'], cp.rel_path)
    if not os.path.exists(file_path):
        abort(404)

    ext = (cp.original_name or '').rsplit('.', 1)[-1].lower() if cp.original_name and '.' in cp.original_name else ''

    if ext in OFFICE_EXTS:
        # 借用 TR 模块已有的 Office→PDF 转换
        try:
            from app.blueprints.tr.routes import _convert_to_pdf, PREVIEW_CACHE_DIR
            cache_dir = os.path.join(current_app.config['UPLOAD_DIR'], PREVIEW_CACHE_DIR)
            pdf_path = _convert_to_pdf(file_path, cache_dir, current_app.logger)
            if pdf_path:
                resp = make_response(send_file(pdf_path, mimetype='application/pdf'))
                resp.headers['Content-Disposition'] = f'inline; filename="{cp.cp_no}.pdf"'
                return resp
        except Exception:
            pass
        return send_file(file_path, as_attachment=True, download_name=cp.original_name, mimetype=cp.mime)

    resp = make_response(send_file(file_path, mimetype=cp.mime or 'application/octet-stream'))
    resp.headers['Content-Disposition'] = f'inline; filename="{cp.original_name}"'
    return resp


# ─────────────────────────────────────────────
# 下载
# ─────────────────────────────────────────────
@cp_bp.route('/<int:cp_id>/download')
def download(cp_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    if not cp.rel_path:
        abort(404)
    file_path = os.path.join(current_app.config['UPLOAD_DIR'], cp.rel_path)
    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True,
                     download_name=cp.original_name or f'{cp.cp_no}.pdf',
                     mimetype=cp.mime)


# ─────────────────────────────────────────────
# 删除
# ─────────────────────────────────────────────
@cp_bp.route('/<int:cp_id>/delete', methods=['POST'])
def delete(cp_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    if cp.rel_path:
        fp = os.path.join(current_app.config['UPLOAD_DIR'], cp.rel_path)
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except OSError:
                pass
    cp_no = cp.cp_no
    db.session.delete(cp)
    db.session.commit()
    flash(f'控制计划 {cp_no} 已删除', 'info')
    return redirect(url_for('cp.index'))


# ─────────────────────────────────────────────
# 编辑（改元数据，可选替换文件）
# ─────────────────────────────────────────────
@cp_bp.route('/<int:cp_id>/edit', methods=['POST'])
def edit(cp_id):
    cp = ControlPlan.query.get_or_404(cp_id)

    new_process = (request.form.get('process_type') or cp.process_type).strip()
    # 改工艺类型时检查唯一约束（同供应商+零件+工艺只能有一份）
    if new_process != cp.process_type:
        clash = ControlPlan.query.filter(
            ControlPlan.supplier_id == cp.supplier_id,
            ControlPlan.part_id == cp.part_id,
            ControlPlan.process_type == new_process,
            ControlPlan.id != cp.id,
        ).first()
        if clash:
            flash(f'该零件已存在「{new_process}」工艺的控制计划，无法重复', 'error')
            return redirect(url_for('cp.index'))
        cp.process_type = new_process

    cp.revision = (request.form.get('revision') or cp.revision).strip()
    cp.notes    = (request.form.get('notes') or '').strip()
    audit_date  = request.form.get('audit_date')
    if audit_date:
        cp.audit_date = date.fromisoformat(audit_date)

    # 可选：替换文件
    file = request.files.get('file')
    if file and file.filename:
        if not _allowed(file.filename):
            flash('仅支持 PDF / Office 文档', 'error')
            return redirect(url_for('cp.index'))
        supplier = cp.supplier
        ext = file.filename.rsplit('.', 1)[1].lower()
        stored_name = f'{uuid.uuid4().hex}.{ext}'
        rel_dir = os.path.join('control_plans', secure_filename(supplier.code))
        full_dir = os.path.join(current_app.config['UPLOAD_DIR'], rel_dir)
        os.makedirs(full_dir, exist_ok=True)
        file_path = os.path.join(full_dir, stored_name)
        file.save(file_path)
        # 删旧文件
        if cp.rel_path:
            old = os.path.join(current_app.config['UPLOAD_DIR'], cp.rel_path)
            if os.path.exists(old):
                try:
                    os.remove(old)
                except OSError:
                    pass
        cp.original_name = file.filename
        cp.stored_name   = stored_name
        cp.rel_path      = os.path.join(rel_dir, stored_name)
        cp.mime          = file.mimetype
        cp.size          = os.path.getsize(file_path)

    cp.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'已更新 {cp.part.pn} 的控制计划', 'success')
    return redirect(url_for('cp.index'))


# ─────────────────────────────────────────────
# AJAX：根据 supplier_id 获取 parts
# ─────────────────────────────────────────────
@cp_bp.route('/api/parts/<int:supplier_id>')
def api_parts(supplier_id):
    parts = Part.query.filter_by(supplier_id=supplier_id).order_by(Part.pn).all()
    return jsonify([{'id': p.id, 'pn': p.pn, 'description': p.description or ''} for p in parts])