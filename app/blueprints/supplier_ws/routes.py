"""
Supplier Workspace — 概览 Dashboard + 各 Tab 路由
替换 app/blueprints/supplier_ws/routes.py
"""
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict
import json

from flask import render_template, abort, redirect, url_for, jsonify
from sqlalchemy import func, or_

from ...models import (
    Supplier, Part, TroubleReport, TRDocument,
    AuditReport, AuditFinding, Drawing, ControlPlan,
)
from ...extensions import db
from . import supplier_ws_bp


def get_supplier_or_404(supplier_code: str) -> Supplier:
    s = Supplier.query.filter_by(code=supplier_code).first()
    if not s:
        abort(404)
    return s


def _supplier_names(supplier):
    """返回该供应商可能被 TR 使用的所有名字"""
    names = set()
    if supplier.name:
        names.add(supplier.name)
    if supplier.chinese_name:
        names.add(supplier.chinese_name)
    return list(names)


def _get_trs(supplier):
    """获取该供应商关联的所有 TR"""
    names = _supplier_names(supplier)
    if not names:
        return []
    return TroubleReport.query.filter(
        TroubleReport.supplier_name.in_(names)
    ).order_by(TroubleReport.created_at.desc()).all()


# ──────────────────────────────────────────────────────────
# 概览 Dashboard
# ──────────────────────────────────────────────────────────

@supplier_ws_bp.route("/<supplier_code>/")
def overview(supplier_code):
    supplier = get_supplier_or_404(supplier_code)
    trs = _get_trs(supplier)

    # ── KPI 统计 ──
    total_trs = len(trs)
    open_trs = sum(1 for t in trs if (t.status or "").lower() not in ("closed", "done", "completed"))
    closed_trs = total_trs - open_trs
    eight_d_pending = sum(1 for t in trs if t.eight_d_status == "NOT_RECEIVED")

    # 扣款汇总（本年）
    current_year = datetime.utcnow().year
    debit_eur = 0.0
    debit_count = 0
    for t in trs:
        if t.debit_amount and t.debit_amount > 0:
            if t.created_at and t.created_at.year == current_year:
                debit_eur += t.debit_amount
                debit_count += 1

    # 零件数
    parts_count = Part.query.filter_by(supplier_id=supplier.id).count()

    # 审核信息
    audits = AuditReport.query.filter(
        or_(
            AuditReport.supplier_id == supplier.id,
            AuditReport.supplier_name.in_(_supplier_names(supplier)),
        )
    ).order_by(AuditReport.audit_date.desc()).all()

    last_audit = audits[0] if audits else None
    open_findings = 0
    for a in audits:
        open_findings += a.open_findings or 0

    # ── 图表数据：近 12 个月 TR 趋势 ──
    now = datetime.utcnow()
    months = []
    for i in range(11, -1, -1):
        d = now - timedelta(days=i * 30)
        months.append(d.strftime("%Y-%m"))
    # 去重保持顺序
    seen = set()
    month_labels = []
    for m in months:
        if m not in seen:
            seen.add(m)
            month_labels.append(m)

    monthly_open = OrderedDict((m, 0) for m in month_labels)
    monthly_closed = OrderedDict((m, 0) for m in month_labels)
    monthly_debit = OrderedDict((m, 0.0) for m in month_labels)

    for t in trs:
        key = t.created_at.strftime("%Y-%m") if t.created_at else None
        if key and key in monthly_open:
            if (t.status or "").lower() in ("closed", "done", "completed"):
                monthly_closed[key] += 1
            else:
                monthly_open[key] += 1
            if t.debit_amount and t.debit_amount > 0:
                monthly_debit[key] += t.debit_amount

    # 短标签 (Jan, Feb...)
    short_labels = []
    for m in month_labels:
        try:
            short_labels.append(datetime.strptime(m, "%Y-%m").strftime("%b"))
        except Exception:
            short_labels.append(m)

    # ── 8D 分布 ──
    eight_d_dist = {"NOT_REQUIRED": 0, "NOT_RECEIVED": 0, "RECEIVED_REJECT": 0, "RECEIVED_PASS": 0}
    for t in trs:
        s = t.eight_d_status or "NOT_REQUIRED"
        if s in eight_d_dist:
            eight_d_dist[s] += 1

    # ── TOP 5 问题零件 ──
    part_issues = defaultdict(int)
    for t in trs:
        if t.part_number:
            part_issues[t.part_number] += 1
    top_parts = sorted(part_issues.items(), key=lambda x: -x[1])[:5]

    # ── 最近活动 ──
    activities = []
    for t in trs[:10]:
        activities.append({
            "date": t.created_at,
            "type": "tr",
            "icon": "🚨",
            "title": f"TR {t.tr_no}",
            "desc": (t.issue_description or "")[:80],
            "status": t.status,
            "url": url_for("tr.edit_tr", tr_id=t.id),
        })
    for a in audits[:5]:
        activities.append({
            "date": a.created_at or datetime(2020, 1, 1),
            "type": "audit",
            "icon": "📋",
            "title": f"Audit {a.audit_no}",
            "desc": f"{a.audit_type or ''} — {a.total_findings or 0} findings",
            "status": a.status,
            "url": "#",
        })
    activities.sort(key=lambda x: x["date"] or datetime(2020, 1, 1), reverse=True)
    activities = activities[:8]

    chart_data = json.dumps({
        "labels": short_labels,
        "open": list(monthly_open.values()),
        "closed": list(monthly_closed.values()),
        "debit": [round(v, 2) for v in monthly_debit.values()],
        "eight_d": eight_d_dist,
        "top_parts_labels": [p[0] for p in top_parts],
        "top_parts_values": [p[1] for p in top_parts],
    })

    return render_template(
        "supplier_ws/overview.html",
        supplier=supplier,
        active="overview",
        # KPIs
        total_trs=total_trs,
        open_trs=open_trs,
        closed_trs=closed_trs,
        eight_d_pending=eight_d_pending,
        debit_eur=debit_eur,
        debit_count=debit_count,
        parts_count=parts_count,
        last_audit=last_audit,
        open_findings=open_findings,
        # Charts
        chart_data=chart_data,
        # Activities
        activities=activities,
    )


# ──────────────────────────────────────────────────────────
# 质量问题 Tab（该供应商的 TR 列表）
# ──────────────────────────────────────────────────────────

@supplier_ws_bp.route("/<supplier_code>/quality")
def quality(supplier_code):
    supplier = get_supplier_or_404(supplier_code)
    trs = _get_trs(supplier)
    return render_template(
        "supplier_ws/quality.html",
        supplier=supplier,
        active="quality",
        trs=trs,
    )


# ──────────────────────────────────────────────────────────
# 扣款 Tab
# ──────────────────────────────────────────────────────────

@supplier_ws_bp.route("/<supplier_code>/debit")
def debit(supplier_code):
    supplier = get_supplier_or_404(supplier_code)
    trs = _get_trs(supplier)
    debit_trs = [t for t in trs if t.debit_amount and t.debit_amount > 0]
    total_debit = sum(t.debit_amount for t in debit_trs)

    return render_template(
        "supplier_ws/debit.html",
        supplier=supplier,
        active="debit",
        debit_trs=debit_trs,
        total_debit=total_debit,
    )


# ──────────────────────────────────────────────────────────
# 审核 Tab
# ──────────────────────────────────────────────────────────

@supplier_ws_bp.route("/<supplier_code>/audits")
def audits(supplier_code):
    supplier = get_supplier_or_404(supplier_code)
    audit_list = AuditReport.query.filter(
        or_(
            AuditReport.supplier_id == supplier.id,
            AuditReport.supplier_name.in_(_supplier_names(supplier)),
        )
    ).order_by(AuditReport.audit_date.desc()).all()

    return render_template(
        "supplier_ws/audits.html",
        supplier=supplier,
        active="audits",
        audits=audit_list,
    )