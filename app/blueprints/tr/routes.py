from flask import render_template, request, redirect, url_for, flash
from sqlalchemy import or_
from . import tr_bp
from ...extensions import db
from ...models import TroubleReport


# 8D 枚举允许值（四态）
ALLOWED_8D_STATUS = {"NOT_REQUIRED", "NOT_RECEIVED", "RECEIVED_REJECT", "RECEIVED_PASS"}

# 用于搜索：把枚举映射成中文关键词（让你在搜索框里输入“未收到/不要求/reject/pass”也能搜到）
EIGHTD_SEARCH_MAP = {
    "NOT_REQUIRED": "不要求",
    "NOT_RECEIVED": "未收到",
    "RECEIVED_REJECT": "reject",
    "RECEIVED_PASS": "pass",
}


@tr_bp.route("/", methods=["GET"])
def index():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = TroubleReport.query

    if q:
        like = f"%{q}%"

        # 额外：支持中文关键词/常用词搜 8D 状态
        # 例如：输入 “未收到” -> 命中 NOT_RECEIVED
        #      输入 “不要求” -> 命中 NOT_REQUIRED
        #      输入 “reject” -> 命中 RECEIVED_REJECT
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

                # 旧字段：编号/链接/备注 也可搜
                TroubleReport.eight_d.ilike(like),

                # ✅ 新字段：8D 状态可搜（同时支持输入枚举值/中文关键词）
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

        # 旧字段：可继续存 8D 编号/链接（可选）
        eight_d = (request.form.get("eight_d") or "").strip() or None

        # ✅ 新字段：8D 状态（四态）
        eight_d_status = (request.form.get("eight_d_status") or "NOT_REQUIRED").strip()
        if eight_d_status not in ALLOWED_8D_STATUS:
            eight_d_status = "NOT_REQUIRED"

        status = (request.form.get("status") or "Open").strip() or "Open"
        remark = (request.form.get("remark") or "").strip() or None

        if not tr_no:
            flash("TR No. 不能为空", "error")
            return render_template("tr/form.html", mode="new", tr=None)

        if not supplier_name:
            flash("SUPPLIER NAME 不能为空", "error")
            return render_template("tr/form.html", mode="new", tr=None)

        if not issue_description:
            flash("ISSUE DESCRIPTION 不能为空", "error")
            return render_template("tr/form.html", mode="new", tr=None)

        exists = TroubleReport.query.filter_by(tr_no=tr_no).first()
        if exists:
            flash(f"TR No. 已存在：{tr_no}", "error")
            return render_template("tr/form.html", mode="new", tr=None)

        tr = TroubleReport(
            tr_no=tr_no,
            supplier_code="N/A",          # 你当前前端不显示 supplier_code，先占位
            supplier_name=supplier_name,
            part_number=part_number,
            part_name=part_name,
            issue_description=issue_description,
            severity=severity,

            eight_d=eight_d,                  # 可选：编号/链接
            eight_d_status=eight_d_status,    # ✅ 关键：四态枚举

            status=status,
            remark=remark,
        )
        db.session.add(tr)
        db.session.commit()

        flash("✅ TR 已创建", "success")
        return redirect(url_for("tr.index"))

    return render_template("tr/form.html", mode="new", tr=None)


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

        # 旧字段：编号/链接（可选）
        eight_d = (request.form.get("eight_d") or "").strip() or None

        # ✅ 新字段：8D 状态（四态）
        eight_d_status = (request.form.get("eight_d_status") or "NOT_REQUIRED").strip()
        if eight_d_status not in ALLOWED_8D_STATUS:
            eight_d_status = "NOT_REQUIRED"

        status = (request.form.get("status") or "Open").strip() or "Open"
        remark = (request.form.get("remark") or "").strip() or None

        if not tr_no:
            flash("TR No. 不能为空", "error")
            return render_template("tr/form.html", mode="edit", tr=tr)

        if not supplier_name:
            flash("SUPPLIER NAME 不能为空", "error")
            return render_template("tr/form.html", mode="edit", tr=tr)

        if not issue_description:
            flash("ISSUE DESCRIPTION 不能为空", "error")
            return render_template("tr/form.html", mode="edit", tr=tr)

        # 如果修改了 TR No，检查唯一性
        if tr_no != tr.tr_no:
            exists = TroubleReport.query.filter_by(tr_no=tr_no).first()
            if exists:
                flash(f"TR No. 已存在：{tr_no}", "error")
                return render_template("tr/form.html", mode="edit", tr=tr)

        tr.tr_no = tr_no
        tr.supplier_name = supplier_name
        tr.part_number = part_number
        tr.part_name = part_name
        tr.issue_description = issue_description
        tr.severity = severity

        tr.eight_d = eight_d
        tr.eight_d_status = eight_d_status   # ✅ 保存新枚举

        tr.status = status
        tr.remark = remark

        db.session.commit()
        flash("✅ TR 已更新", "success")
        return redirect(url_for("tr.index"))

    return render_template("tr/form.html", mode="edit", tr=tr)


@tr_bp.route("/<int:tr_id>/delete", methods=["POST"])
def delete_tr(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    db.session.delete(tr)
    db.session.commit()
    flash("✅ TR 已删除", "success")
    return redirect(url_for("tr.index"))
