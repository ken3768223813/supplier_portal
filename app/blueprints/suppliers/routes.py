from flask import render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_, case
from datetime import datetime, timedelta

from . import suppliers_bp
from ...extensions import db
from ...models import Supplier, Part, TroubleReport


# 头像调色板
AVATAR_PALETTE = [
    ("bg-blue-100", "text-blue-700"),
    ("bg-purple-100", "text-purple-700"),
    ("bg-pink-100", "text-pink-700"),
    ("bg-orange-100", "text-orange-700"),
    ("bg-green-100", "text-green-700"),
    ("bg-cyan-100", "text-cyan-700"),
    ("bg-amber-100", "text-amber-700"),
    ("bg-emerald-100", "text-emerald-700"),
    ("bg-indigo-100", "text-indigo-700"),
    ("bg-rose-100", "text-rose-700"),
]


def _avatar_for(text: str):
    """根据字符串确定性地选一个颜色"""
    if not text:
        return AVATAR_PALETTE[0]
    h = sum(ord(c) for c in text) % len(AVATAR_PALETTE)
    return AVATAR_PALETTE[h]


def _avatar_letter(supplier):
    """取头像显示的字符：优先中文名第一个字，否则英文首字母"""
    if supplier.chinese_name:
        return supplier.chinese_name[0]
    if supplier.name:
        return supplier.name[0].upper()
    return supplier.code[0].upper() if supplier.code else "?"


def _enrich_suppliers(suppliers):
    """为每个供应商附加统计信息"""
    if not suppliers:
        return []

    # ── 批量查询：零件数 ──
    supplier_ids = [s.id for s in suppliers]
    parts_counts = dict(
        db.session.query(Part.supplier_id, func.count(Part.id))
        .filter(Part.supplier_id.in_(supplier_ids))
        .group_by(Part.supplier_id).all()
    )

    # ── 批量查询：TR 统计（按 supplier_name 匹配） ──
    # 收集所有可能的名字
    all_names = set()
    name_to_supplier = {}
    for s in suppliers:
        if s.name:
            all_names.add(s.name)
            name_to_supplier[s.name] = s.id
        if s.chinese_name:
            all_names.add(s.chinese_name)
            name_to_supplier[s.chinese_name] = s.id

    # 一次查所有相关 TR
    tr_stats = {}  # supplier_id -> {open, closed, debit, last_activity}
    if all_names:
        trs = TroubleReport.query.filter(
            TroubleReport.supplier_name.in_(all_names)
        ).all()
        for tr in trs:
            sid = name_to_supplier.get(tr.supplier_name)
            if sid is None:
                continue
            if sid not in tr_stats:
                tr_stats[sid] = {"open": 0, "closed": 0, "debit": 0.0, "last": None}

            st = (tr.status or "").lower()
            if st in ("closed", "done", "completed"):
                tr_stats[sid]["closed"] += 1
            else:
                tr_stats[sid]["open"] += 1

            if tr.debit_amount and tr.debit_amount > 0:
                tr_stats[sid]["debit"] += tr.debit_amount

            if tr.created_at:
                cur = tr_stats[sid]["last"]
                if cur is None or tr.created_at > cur:
                    tr_stats[sid]["last"] = tr.created_at

    # ── 组装结果 ──
    enriched = []
    for s in suppliers:
        stats = tr_stats.get(s.id, {"open": 0, "closed": 0, "debit": 0.0, "last": None})
        bg, fg = _avatar_for(s.code or s.name or "")

        # 状态：red(4+) / yellow(1-3) / green(0)
        if stats["open"] >= 4:
            status_color = "red"
        elif stats["open"] >= 1:
            status_color = "yellow"
        else:
            status_color = "green"

        enriched.append({
            "supplier": s,
            "open_trs": stats["open"],
            "closed_trs": stats["closed"],
            "total_trs": stats["open"] + stats["closed"],
            "debit": stats["debit"],
            "last_activity": stats["last"],
            "parts_count": parts_counts.get(s.id, 0),
            "avatar_letter": _avatar_letter(s),
            "avatar_bg": bg,
            "avatar_fg": fg,
            "status_color": status_color,
        })
    return enriched


@suppliers_bp.get("/")
def index():
    q = request.args.get("q", "").strip()
    filter_mode = request.args.get("filter", "all")  # all / issues / quiet / recent
    sort_mode = request.args.get("sort", "recent")     # name / recent / issues

    query = Supplier.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Supplier.code.ilike(like)) |
            (Supplier.name.ilike(like)) |
            (Supplier.chinese_name.ilike(like))
        )

    suppliers = query.all()
    enriched = _enrich_suppliers(suppliers)

    # 客户端筛选
    if filter_mode == "issues":
        enriched = [e for e in enriched if e["open_trs"] > 0]
    elif filter_mode == "quiet":
        enriched = [e for e in enriched if e["open_trs"] == 0]
    elif filter_mode == "recent":
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        enriched = [
            e for e in enriched
            if e["last_activity"] and e["last_activity"] > seven_days_ago
        ]

    # 排序
    if sort_mode == "recent":
        enriched.sort(key=lambda e: e["last_activity"] or datetime(2000, 1, 1), reverse=True)
    elif sort_mode == "issues":
        enriched.sort(key=lambda e: -e["open_trs"])
    else:  # name (按 code)
        enriched.sort(key=lambda e: e["supplier"].code or "")

    # 全局统计（不受 filter 影响）
    all_enriched = _enrich_suppliers(Supplier.query.all())
    total_count = len(all_enriched)
    issues_count = sum(1 for e in all_enriched if e["open_trs"] > 0)
    quiet_count = sum(1 for e in all_enriched if e["open_trs"] == 0)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_count = sum(
        1 for e in all_enriched
        if e["last_activity"] and e["last_activity"] > seven_days_ago
    )

    return render_template(
        "suppliers/index.html",
        suppliers=enriched,
        q=q,
        filter_mode=filter_mode,
        sort_mode=sort_mode,
        stats={
            "total": total_count,
            "issues": issues_count,
            "quiet": quiet_count,
            "recent": recent_count,
        },
    )


@suppliers_bp.post("/add")
def add():
    code = request.form.get("code", "").strip()
    name = request.form.get("name", "").strip()

    if not code or not name:
        flash("Supplier code 和 name 都需要填写。", "warning")
        return redirect(url_for("suppliers.index"))

    if Supplier.query.filter_by(code=code).first():
        flash(f"供应商 {code} 已存在。", "warning")
        return redirect(url_for("suppliers.index"))

    db.session.add(Supplier(code=code, name=name))
    db.session.commit()
    flash(f"已添加供应商：{code}", "success")
    return redirect(url_for("suppliers.index"))


@suppliers_bp.route("/new", methods=["GET", "POST"])
def new_supplier():
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        chinese_name = request.form.get("chinese_name", "").strip() or None

        if not code:
            flash("供应商代码不能为空", "error")
            return render_template("suppliers/new.html")

        if Supplier.query.filter_by(code=code).first():
            flash(f"供应商代码已存在：{code}", "error")
            return render_template("suppliers/new.html")

        s = Supplier(code=code, name=name, chinese_name=chinese_name)
        db.session.add(s)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("保存失败：供应商代码可能重复", "error")
            return render_template("suppliers/new.html")

        flash("✅ 供应商已新增", "success")
        return redirect(url_for("suppliers.index"))

    return render_template("suppliers/new.html")


@suppliers_bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if request.method == "POST":
        supplier.code = request.form.get("code", "").strip() or supplier.code
        supplier.name = request.form.get("name", "").strip() or supplier.name
        supplier.chinese_name = request.form.get("chinese_name", "").strip() or None
        db.session.commit()
        flash("已更新", "success")
        return redirect(url_for("suppliers.index"))
    return render_template("suppliers/edit.html", supplier=supplier)


@suppliers_bp.post("/<int:supplier_id>/delete")
def delete_supplier(supplier_id):
    s = Supplier.query.get_or_404(supplier_id)
    db.session.delete(s)
    db.session.commit()
    flash(f"已删除供应商：{s.code}", "success")
    return redirect(url_for("suppliers.index"))