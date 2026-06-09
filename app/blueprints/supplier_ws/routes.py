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

# ──────────────────────────────────────────────────────────
# 单供应商质量报告（打印 / 导出 PDF）
#   用法：把这段加到 supplier_ws/routes.py 末尾
#   依赖文件顶部已 import 的：render_template, request(需补), Supplier, TroubleReport
#   若顶部没 import request，请加上： from flask import request
# ──────────────────────────────────────────────────────────
from datetime import date as _date, datetime as _datetime
from collections import Counter, OrderedDict
from flask import request


def _tr_effective_date(tr):
    """TR 的有效日期：优先取 remark 末段的 dd.mm.yyyy，否则用 created_at"""
    if tr.remark and "|" in tr.remark:
        seg = tr.remark.split("|")[-1].strip()
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return _datetime.strptime(seg, fmt).date()
            except ValueError:
                continue
    if tr.created_at:
        return tr.created_at.date()
    return None


def _resolve_period(period, custom_start, custom_end):
    """返回 (start_date, end_date, 中文标签)；start/end 为 None 表示不限"""
    today = _date.today()
    if period == "this_month":
        start = today.replace(day=1)
        return start, today, f"{start.year}年{start.month}月"
    if period == "this_quarter":
        q = (today.month - 1) // 3
        start = _date(today.year, q * 3 + 1, 1)
        return start, today, f"{start.year}年 Q{q + 1}"
    if period == "this_half":
        if today.month <= 6:
            return _date(today.year, 1, 1), today, f"{today.year}年 上半年"
        return _date(today.year, 7, 1), today, f"{today.year}年 下半年"
    if period == "this_year":
        return _date(today.year, 1, 1), today, f"{today.year}年"
    if period == "custom" and custom_start and custom_end:
        try:
            s = _datetime.strptime(custom_start, "%Y-%m-%d").date()
            e = _datetime.strptime(custom_end, "%Y-%m-%d").date()
            return s, e, f"{s.strftime('%Y/%m/%d')} – {e.strftime('%Y/%m/%d')}"
        except ValueError:
            pass
    return None, None, "全部时间"


@supplier_ws_bp.route("/<supplier_code>/report")
def report(supplier_code):
    supplier = get_supplier_or_404(supplier_code)
    period = request.args.get("period", "this_year")
    custom_start = request.args.get("start", "")
    custom_end = request.args.get("end", "")

    start, end, period_label = _resolve_period(period, custom_start, custom_end)

    all_trs = _get_trs(supplier)  # 已按 created_at 倒序

    # 按周期过滤
    def in_period(tr):
        if start is None:
            return True
        d = _tr_effective_date(tr)
        return d is not None and start <= d <= end

    trs = [t for t in all_trs if in_period(t)]

    # ── KPI ──
    total = len(trs)
    closed = sum(1 for t in trs if (t.status or "").lower() in ("closed", "done", "completed"))
    open_cnt = total - closed
    pending_8d = sum(1 for t in trs if t.eight_d_status == "NOT_RECEIVED")
    debit_total = sum(t.debit_amount for t in trs if t.debit_amount) or 0

    # ── 环比（仅固定周期）──
    prev_total = None
    if start is not None and period != "custom":
        span = (end - start).days
        prev_end = start.replace(day=1) if False else (start - __import__("datetime").timedelta(days=1))
        prev_start = prev_end - __import__("datetime").timedelta(days=span)
        prev_total = sum(1 for t in all_trs
                         if (_tr_effective_date(t) or _date(1900, 1, 1)) >= prev_start
                         and (_tr_effective_date(t) or _date(1900, 1, 1)) <= prev_end)

    # ── 月度趋势 ──
    month_counter = Counter()
    for t in trs:
        d = _tr_effective_date(t)
        if d:
            month_counter[(d.year, d.month)] += 1
    if month_counter:
        keys = sorted(month_counter.keys())
        # 补齐区间内空月
        months = OrderedDict()
        y, m = keys[0]
        ey, em = keys[-1]
        while (y, m) <= (ey, em):
            months[(y, m)] = month_counter.get((y, m), 0)
            m += 1
            if m > 12:
                m = 1; y += 1
        monthly = [{"label": f"{k[1]}月", "count": v} for k, v in months.items()]
    else:
        monthly = []
    month_max = max([x["count"] for x in monthly], default=1) or 1

    # ── 8D 状态分布 ──
    d8_map = {"NOT_REQUIRED": "不要求", "NOT_RECEIVED": "未收到", "RECEIVED_REJECT": "已收到(拒收)", "RECEIVED_PASS": "已收到(通过)"}
    d8_counter = Counter((t.eight_d_status or "NOT_REQUIRED") for t in trs)
    eight_d = [{"key": k, "label": d8_map.get(k, k), "count": d8_counter.get(k, 0)}
               for k in ["NOT_RECEIVED", "RECEIVED_REJECT", "RECEIVED_PASS", "NOT_REQUIRED"]]

    # ── Top 问题零件 ──
    part_counter = Counter()
    part_name_map = {}
    for t in trs:
        pn = t.part_number or "（未填零件号）"
        part_counter[pn] += 1
        if pn not in part_name_map and t.part_name:
            part_name_map[pn] = t.part_name
    top_parts = [{"pn": pn, "name": part_name_map.get(pn, ""), "count": c}
                 for pn, c in part_counter.most_common(8)]
    top_max = max([p["count"] for p in top_parts], default=1) or 1

    # ── 评级 ──
    if open_cnt >= 4:
        rating = {"label": "需重点关注", "color": "red"}
    elif open_cnt >= 1:
        rating = {"label": "持续跟进", "color": "amber"}
    else:
        rating = {"label": "表现良好", "color": "green"}

    # TR 列表（按日期倒序，未闭环优先）
    trs_sorted = sorted(
        trs,
        key=lambda t: ((t.status or "").lower() in ("closed", "done", "completed"),
                       -(( _tr_effective_date(t) or _date(1900, 1, 1)).toordinal())),
    )

    return render_template(
        "supplier_ws/report.html",
        supplier=supplier,
        period=period, period_label=period_label,
        custom_start=custom_start, custom_end=custom_end,
        total=total, open_cnt=open_cnt, closed=closed,
        pending_8d=pending_8d, debit_total=debit_total,
        prev_total=prev_total,
        monthly=monthly, month_max=month_max,
        eight_d=eight_d,
        top_parts=top_parts, top_max=top_max,
        rating=rating,
        trs=trs_sorted,
        tr_date=_tr_effective_date,
        generated_at=_datetime.now(),
    )