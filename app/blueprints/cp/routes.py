from flask import render_template, request, redirect, url_for, flash, jsonify
from app.extensions import db
from app.models import ControlPlan, ProcessStep, ControlCharacteristic, Supplier, Part
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

UNIT_OPTIONS = ['°C', 'MPa', 'bar', 'mm', 'μm', 's', 'min', 'h', 'rpm', 'N', 'kN', '%', 'kg', 'g', '—']
FREQUENCY_OPTIONS = ['每件', '每批次', '首件', '每小时', '每班', '连续', '抽检']


# ─────────────────────────────────────────────
# 列表页
# ─────────────────────────────────────────────
@cp_bp.route('/')
def index():
    process_type = request.args.get('process_type', '')
    supplier_id  = request.args.get('supplier_id', '')
    q            = request.args.get('q', '')

    query = ControlPlan.query.join(Part).join(Supplier)

    if process_type:
        query = query.filter(ControlPlan.process_type == process_type)
    if supplier_id:
        query = query.filter(ControlPlan.supplier_id == int(supplier_id))
    if q:
        query = query.filter(
            Part.pn.ilike(f'%{q}%') |
            Part.description.ilike(f'%{q}%') |
            Supplier.name.ilike(f'%{q}%')
        )

    cps       = query.order_by(ControlPlan.updated_at.desc()).all()
    suppliers = Supplier.query.order_by(Supplier.name).all()

    return render_template('cp/index.html',
                           cps=cps,
                           suppliers=suppliers,
                           process_types=PROCESS_TYPES,
                           selected_type=process_type,
                           selected_supplier=supplier_id,
                           q=q)


# ─────────────────────────────────────────────
# 新建 CP
# ─────────────────────────────────────────────
@cp_bp.route('/new', methods=['GET', 'POST'])
def new():
    suppliers = Supplier.query.order_by(Supplier.name).all()

    if request.method == 'POST':
        supplier_id  = int(request.form['supplier_id'])
        part_id      = int(request.form['part_id'])
        process_type = request.form['process_type']
        audit_date   = request.form.get('audit_date') or None
        auditor      = request.form.get('auditor', '')
        notes        = request.form.get('notes', '')

        existing = ControlPlan.query.filter_by(
            supplier_id=supplier_id,
            part_id=part_id,
            process_type=process_type
        ).first()
        if existing:
            flash(f'该供应商/零件已存在控制计划 {existing.cp_no}，请直接编辑。', 'warning')
            return redirect(url_for('cp.edit', cp_id=existing.id))

        supplier = Supplier.query.get(supplier_id)
        part     = Part.query.get(part_id)
        cp_no = f'CP-{supplier.code}-{part.pn}-{process_type}'.upper()[:50]

        cp = ControlPlan(
            supplier_id  = supplier_id,
            part_id      = part_id,
            cp_no        = cp_no,
            process_type = process_type,
            audit_date   = date.fromisoformat(audit_date) if audit_date else None,
            auditor      = auditor,
            notes        = notes,
            status       = 'active',
        )
        db.session.add(cp)
        db.session.flush()

        _save_steps_from_form(cp.id, request.form)

        db.session.commit()
        flash(f'控制计划 {cp.cp_no} 创建成功！', 'success')
        return redirect(url_for('cp.detail', cp_id=cp.id))

    return render_template('cp/form.html',
                           cp=None,
                           suppliers=suppliers,
                           process_types=PROCESS_TYPES,
                           unit_options=UNIT_OPTIONS,
                           frequency_options=FREQUENCY_OPTIONS)


# ─────────────────────────────────────────────
# 详情页
# ─────────────────────────────────────────────
@cp_bp.route('/<int:cp_id>')
def detail(cp_id):
    cp    = ControlPlan.query.get_or_404(cp_id)
    steps = cp.steps.all()
    for step in steps:
        step._chars = step.characteristics.all()
    return render_template('cp/detail.html', cp=cp, steps=steps)


# ─────────────────────────────────────────────
# 编辑 CP
# ─────────────────────────────────────────────
@cp_bp.route('/<int:cp_id>/edit', methods=['GET', 'POST'])
def edit(cp_id):
    cp        = ControlPlan.query.get_or_404(cp_id)
    suppliers = Supplier.query.order_by(Supplier.name).all()

    if request.method == 'POST':
        cp.process_type = request.form['process_type']
        cp.auditor      = request.form.get('auditor', cp.auditor)
        cp.notes        = request.form.get('notes', '')
        audit_date      = request.form.get('audit_date')
        if audit_date:
            cp.audit_date = date.fromisoformat(audit_date)
        cp.updated_at   = datetime.utcnow()

        # ── 先明确删除旧特性，再删工序，防止级联残留 ──
        old_step_ids = [s.id for s in cp.steps.all()]
        if old_step_ids:
            ControlCharacteristic.query.filter(
                ControlCharacteristic.step_id.in_(old_step_ids)
            ).delete(synchronize_session=False)

        ProcessStep.query.filter_by(cp_id=cp.id).delete(synchronize_session=False)
        db.session.flush()

        _save_steps_from_form(cp.id, request.form)

        db.session.commit()
        flash('控制计划已更新', 'success')
        return redirect(url_for('cp.detail', cp_id=cp.id))

    steps = cp.steps.all()
    for step in steps:
        step._chars = step.characteristics.all()

    return render_template('cp/form.html',
                           cp=cp,
                           steps=steps,
                           suppliers=suppliers,
                           process_types=PROCESS_TYPES,
                           unit_options=UNIT_OPTIONS,
                           frequency_options=FREQUENCY_OPTIONS)


# ─────────────────────────────────────────────
# 删除 CP
# ─────────────────────────────────────────────
@cp_bp.route('/<int:cp_id>/delete', methods=['POST'])
def delete(cp_id):
    cp = ControlPlan.query.get_or_404(cp_id)
    db.session.delete(cp)
    db.session.commit()
    flash(f'控制计划 {cp.cp_no} 已删除', 'info')
    return redirect(url_for('cp.index'))


# ─────────────────────────────────────────────
# 对比页
# ─────────────────────────────────────────────
@cp_bp.route('/compare')
def compare():
    pn           = request.args.get('pn', '').strip()
    selected_ids = request.args.getlist('cp_ids', type=int)

    matching_cps = []

    if pn:
        parts    = Part.query.filter(Part.pn.ilike(f'%{pn}%')).all()
        part_ids = [p.id for p in parts]
        matching_cps = ControlPlan.query.filter(
            ControlPlan.part_id.in_(part_ids),
            ControlPlan.status == 'active'
        ).order_by(ControlPlan.supplier_id).all()

    compare_cps = []
    if selected_ids:
        compare_cps = ControlPlan.query.filter(ControlPlan.id.in_(selected_ids)).all()

    comparison = _build_comparison(compare_cps) if len(compare_cps) >= 2 else None

    return render_template('cp/compare.html',
                           pn=pn,
                           matching_cps=matching_cps,
                           selected_ids=selected_ids,
                           compare_cps=compare_cps,
                           comparison=comparison)


# ─────────────────────────────────────────────
# AJAX：根据 supplier_id 获取 parts
# ─────────────────────────────────────────────
@cp_bp.route('/api/parts/<int:supplier_id>')
def api_parts(supplier_id):
    parts = Part.query.filter_by(supplier_id=supplier_id).order_by(Part.pn).all()
    return jsonify([{'id': p.id, 'pn': p.pn, 'description': p.description or ''} for p in parts])


# ─────────────────────────────────────────────
# 私有辅助函数
# ─────────────────────────────────────────────
def _save_steps_from_form(cp_id, form):
    step_idx = 0
    while f'step_name_{step_idx}' in form:
        name = form.get(f'step_name_{step_idx}', '').strip()
        if not name:
            step_idx += 1
            continue

        seq  = int(form.get(f'step_seq_{step_idx}', (step_idx + 1) * 10))
        step = ProcessStep(
            cp_id          = cp_id,
            seq            = seq,
            process_name   = name,
            process_code   = form.get(f'step_code_{step_idx}', '').strip(),
            machine        = form.get(f'step_machine_{step_idx}', '').strip(),
            is_key_process = f'step_kp_{step_idx}' in form,
            notes          = form.get(f'step_notes_{step_idx}', '').strip(),
        )
        db.session.add(step)
        db.session.flush()

        char_idx = 0
        while f'char_name_{step_idx}_{char_idx}' in form:
            cname = form.get(f'char_name_{step_idx}_{char_idx}', '').strip()
            if cname:
                char = ControlCharacteristic(
                    step_id        = step.id,
                    char_name      = cname,
                    spec_value     = form.get(f'char_spec_{step_idx}_{char_idx}', '').strip(),
                    spec_unit      = form.get(f'char_unit_{step_idx}_{char_idx}', '').strip(),
                    tolerance      = form.get(f'char_tol_{step_idx}_{char_idx}',  '').strip(),
                    control_method = form.get(f'char_method_{step_idx}_{char_idx}', '').strip(),
                    sample_size    = form.get(f'char_size_{step_idx}_{char_idx}', '').strip(),
                    frequency      = form.get(f'char_freq_{step_idx}_{char_idx}', '').strip(),
                    reaction_plan  = form.get(f'char_reaction_{step_idx}_{char_idx}', '').strip(),
                    is_key_char    = f'char_kcc_{step_idx}_{char_idx}' in form,
                )
                db.session.add(char)
            char_idx += 1

        step_idx += 1


def _build_comparison(cps):
    all_process_names = []
    seen = set()
    for cp in cps:
        for step in cp.steps.order_by(ProcessStep.seq).all():
            if step.process_name not in seen:
                all_process_names.append(step.process_name)
                seen.add(step.process_name)

    rows = []
    for pname in all_process_names:
        steps_per_cp = []
        for cp in cps:
            step = cp.steps.filter_by(process_name=pname).first()
            steps_per_cp.append(step)

        is_key = any(s.is_key_process for s in steps_per_cp if s)

        all_char_names = []
        seen_c = set()
        for step in steps_per_cp:
            if step:
                for c in step.characteristics.all():
                    if c.char_name not in seen_c:
                        all_char_names.append(c.char_name)
                        seen_c.add(c.char_name)

        chars = {}
        for cname in all_char_names:
            cell_data = []
            specs = []
            for step in steps_per_cp:
                if step:
                    char = step.characteristics.filter_by(char_name=cname).first()
                    if char:
                        spec_str = char.spec_display()
                        cell_data.append({'spec': spec_str, 'method': char.control_method or '—', 'freq': char.frequency or '—'})
                        specs.append(spec_str)
                    else:
                        cell_data.append(None)
                        specs.append(None)
                else:
                    cell_data.append(None)
                    specs.append(None)

            filled   = [s for s in specs if s]
            has_diff = len(set(filled)) > 1

            for cell in cell_data:
                if cell:
                    cell['diff'] = has_diff

            chars[cname] = cell_data

        rows.append({
            'process_name': pname,
            'is_key': is_key,
            'chars': chars,
        })

    return {'headers': cps, 'rows': rows}