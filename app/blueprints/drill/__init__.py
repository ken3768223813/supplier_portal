"""Desktop-first SQE English Lab."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import json

from flask import (
    Blueprint, Response, abort, current_app, flash, jsonify, redirect,
    render_template, request, url_for,
)
from sqlalchemy import func, or_

from ...drill_helper import generate_sqe_cards, schedule_review
from ...extensions import db
from ...models import (
    ControlPlan, DrillAttempt, DrillPhrase, DrillProgress, TroubleReport,
)


drill_bp = Blueprint("drill", __name__, url_prefix="/drill")

SCENARIOS = [
    {
        "value": "meeting",
        "label": "会议沟通",
        "en": "Meetings",
        "description": "开场、澄清、总结、确认责任与完成时间。",
        "accent": "blue",
    },
    {
        "value": "audit",
        "label": "供应商审核",
        "en": "Supplier Audit",
        "description": "追问过程、索取证据、说明审核发现。",
        "accent": "amber",
    },
    {
        "value": "factory",
        "label": "工厂与工艺",
        "en": "Factory & Process",
        "description": "介绍生产流程、设备、检验方法和关键参数。",
        "accent": "emerald",
    },
    {
        "value": "quality",
        "label": "质量问题",
        "en": "Quality Issue",
        "description": "描述缺陷、批次风险、隔离和临时措施。",
        "accent": "red",
    },
    {
        "value": "eight_d",
        "label": "8D 改善",
        "en": "8D Improvement",
        "description": "讨论根本原因、流出原因、措施与效果验证。",
        "accent": "violet",
    },
    {
        "value": "interpreting",
        "label": "陪同与口译",
        "en": "Interpreting",
        "description": "转述问题、确认意思并连接中外双方表达。",
        "accent": "cyan",
    },
    {
        "value": "claim",
        "label": "扣款与索赔",
        "en": "Claims",
        "description": "确认责任、费用构成、扣款与供应商确认。",
        "accent": "orange",
    },
    {
        "value": "urgent",
        "label": "紧急处置",
        "en": "Urgent Response",
        "description": "停线、库存隔离、加急检查和问题升级。",
        "accent": "rose",
    },
]
SCENARIO_MAP = {item["value"]: item for item in SCENARIOS}
CATEGORY_CHOICES = [(item["value"], item["label"]) for item in SCENARIOS]
VALID_CATEGORIES = set(SCENARIO_MAP)

MODES = [
    ("quick", "快速反应"),
    ("listening", "听力理解"),
    ("assembly", "表达组装"),
]
VALID_MODES = {item[0] for item in MODES}


def _approved_query():
    return DrillPhrase.query.filter_by(active=True, status="approved")


def _streak_days():
    recent = (
        DrillAttempt.query.with_entities(DrillAttempt.created_at)
        .order_by(DrillAttempt.created_at.desc())
        .limit(500)
        .all()
    )
    practiced = {row.created_at.date() for row in recent if row.created_at}
    cursor = date.today()
    if cursor not in practiced:
        cursor -= timedelta(days=1)
    streak = 0
    while cursor in practiced:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _session_phrases(category, limit=12):
    today = date.today()
    query = _approved_query()
    if category:
        query = query.filter(DrillPhrase.category == category)
    due = (
        query.outerjoin(DrillProgress, DrillProgress.phrase_id == DrillPhrase.id)
        .filter(or_(DrillProgress.id.is_(None), DrillProgress.due_date <= today))
        .order_by(DrillProgress.due_date.asc(), func.random())
        .limit(limit)
        .all()
    )
    if due:
        return due
    return query.order_by(func.random()).limit(min(limit, 8)).all()


def _source_payload(source_ref):
    try:
        source_type, raw_id = source_ref.split(":", 1)
        source_id = int(raw_id)
    except (AttributeError, TypeError, ValueError):
        return None

    if source_type in {"tr", "eight_d"}:
        tr = db.session.get(TroubleReport, source_id)
        if not tr:
            return None
        if source_type == "tr":
            text = "\n".join(
                value for value in (
                    f"Issue: {tr.issue_summary or tr.issue_description or ''}",
                    f"Part: {tr.part_name or ''}",
                    f"Status: {tr.status or ''}",
                    f"8D status: {tr.eight_d_status or ''}",
                ) if value.split(":", 1)[-1].strip()
            )
            return {
                "type": "tr",
                "id": str(tr.id),
                "label": tr.tr_no,
                "category": "quality",
                "text": text,
            }
        text = "\n".join(
            value for value in (
                f"Issue: {tr.issue_summary or tr.issue_description or ''}",
                f"Occurrence root cause: {tr.eight_d_root_cause or ''}",
                f"Escape root cause: {tr.eight_d_escape_cause or ''}",
                f"Corrective action: {tr.eight_d_action or ''}",
                f"Escape action: {tr.eight_d_escape_action or ''}",
            ) if value.split(":", 1)[-1].strip()
        )
        return {
            "type": "eight_d",
            "id": str(tr.id),
            "label": f"{tr.tr_no} · 8D",
            "category": "eight_d",
            "text": text,
        }

    if source_type == "cp":
        cp = db.session.get(ControlPlan, source_id)
        if not cp:
            return None
        version = cp.versions.first()
        try:
            data = json.loads(version.structured_json or "{}") if version else {}
        except (TypeError, ValueError):
            data = {}
        lines = []
        for step in (data.get("steps") or [])[:25]:
            process_name = step.get("process_name") or ""
            machine = step.get("machine") or ""
            if process_name:
                lines.append(f"Process: {process_name}; Equipment: {machine}")
            for item in (step.get("characteristics") or [])[:3]:
                lines.append(
                    "Characteristic: {name}; Specification: {spec}; "
                    "Measurement: {measurement}; Control: {control}".format(
                        name=item.get("char_name") or "",
                        spec=item.get("spec_value") or "",
                        measurement=item.get("measurement_method") or "",
                        control=item.get("control_method") or "",
                    )
                )
        return {
            "type": "cp",
            "id": str(cp.id),
            "label": cp.cp_no,
            "category": "factory",
            "text": "\n".join(lines),
        }
    return None


@drill_bp.route("/")
def index():
    category = request.args.get("category", "").strip()
    if category not in VALID_CATEGORIES:
        category = ""
    mode = request.args.get("mode", "quick").strip()
    if mode not in VALID_MODES:
        mode = "quick"

    phrases = _session_phrases(category)
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_attempts = DrillAttempt.query.filter(
        DrillAttempt.created_at >= today_start
    ).count()
    due_count = (
        _approved_query()
        .outerjoin(DrillProgress, DrillProgress.phrase_id == DrillPhrase.id)
        .filter(or_(DrillProgress.id.is_(None), DrillProgress.due_date <= date.today()))
        .count()
    )
    mastered_count = (
        DrillProgress.query.join(DrillPhrase)
        .filter(
            DrillPhrase.active.is_(True),
            DrillPhrase.status == "approved",
            DrillProgress.repetitions >= 3,
            DrillProgress.interval_days >= 14,
        )
        .count()
    )
    return render_template(
        "drill/index.html",
        scenarios=SCENARIOS,
        scenario_map=SCENARIO_MAP,
        modes=MODES,
        current_category=category,
        current_mode=mode,
        phrases=[phrase.to_dict() for phrase in phrases],
        due_count=due_count,
        today_attempts=today_attempts,
        mastered_count=mastered_count,
        streak=_streak_days(),
    )


@drill_bp.route("/scenarios")
def scenarios():
    today = date.today()
    scenario_rows = []
    for scenario in SCENARIOS:
        base = _approved_query().filter(DrillPhrase.category == scenario["value"])
        total = base.count()
        due = (
            base.outerjoin(DrillProgress, DrillProgress.phrase_id == DrillPhrase.id)
            .filter(or_(DrillProgress.id.is_(None), DrillProgress.due_date <= today))
            .count()
        )
        practiced = (
            DrillProgress.query.join(DrillPhrase)
            .filter(
                DrillPhrase.category == scenario["value"],
                DrillProgress.attempts > 0,
            )
            .count()
        )
        row = dict(scenario)
        row.update({"total": total, "due": due, "practiced": practiced})
        scenario_rows.append(row)
    return render_template("drill/scenarios.html", scenarios=scenario_rows)


@drill_bp.route("/materials")
def materials():
    status = request.args.get("status", "pending").strip()
    if status not in {"pending", "approved", "all"}:
        status = "pending"
    page = request.args.get("page", 1, type=int)
    query = DrillPhrase.query.filter(DrillPhrase.active.is_(True))
    if status != "all":
        query = query.filter(DrillPhrase.status == status)
    pagination = query.order_by(DrillPhrase.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    phrases = pagination.items

    latest_trs = TroubleReport.query.order_by(TroubleReport.created_at.desc()).limit(30).all()
    eight_d_trs = (
        TroubleReport.query.filter(
            or_(
                TroubleReport.eight_d_root_cause.isnot(None),
                TroubleReport.eight_d_action.isnot(None),
            )
        )
        .order_by(TroubleReport.updated_at.desc())
        .limit(30)
        .all()
    )
    control_plans = ControlPlan.query.order_by(ControlPlan.updated_at.desc()).limit(30).all()
    counts = {
        item: DrillPhrase.query.filter_by(active=True, status=item).count()
        for item in ("pending", "approved")
    }
    return render_template(
        "drill/materials.html",
        phrases=phrases,
        scenarios=SCENARIOS,
        category_map=SCENARIO_MAP,
        current_status=status,
        pagination=pagination,
        counts=counts,
        latest_trs=latest_trs,
        eight_d_trs=eight_d_trs,
        control_plans=control_plans,
    )


@drill_bp.route("/api/rate", methods=["POST"])
def rate():
    payload = request.get_json(silent=True) or {}
    phrase = db.session.get(DrillPhrase, payload.get("phrase_id"))
    rating = str(payload.get("rating") or "").strip()
    mode = str(payload.get("mode") or "quick").strip()
    if not phrase or not phrase.active or phrase.status != "approved":
        abort(404)
    if mode not in VALID_MODES:
        mode = "quick"
    try:
        result = schedule_review(phrase.progress, rating)
    except ValueError:
        return jsonify({"ok": False, "message": "Invalid rating"}), 400

    progress = phrase.progress or DrillProgress(phrase=phrase)
    progress.ease_factor = result["ease_factor"]
    progress.interval_days = result["interval_days"]
    progress.repetitions = result["repetitions"]
    progress.due_date = result["due_date"]
    progress.attempts = (progress.attempts or 0) + 1
    if rating != "again":
        progress.successes = (progress.successes or 0) + 1
    progress.last_rating = rating
    progress.last_mode = mode
    progress.last_practiced_at = datetime.utcnow()
    db.session.add(progress)
    db.session.add(
        DrillAttempt(
            phrase=phrase,
            mode=mode,
            rating=rating,
            correct=payload.get("correct"),
            response_text=str(payload.get("response") or "")[:1000] or None,
        )
    )
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "due": progress.due_date.isoformat(),
            "interval_days": progress.interval_days,
        }
    )


@drill_bp.route("/generate", methods=["POST"])
def generate():
    source = _source_payload((request.form.get("source_ref") or "").strip())
    if not source or not source["text"].strip():
        flash("没有找到可用于生成训练素材的业务内容。", "error")
        return redirect(url_for("drill.materials"))
    category = (request.form.get("category") or source["category"]).strip()
    if category not in VALID_CATEGORIES:
        category = source["category"]
    cards = generate_sqe_cards(
        source["text"],
        source["label"],
        category,
        VALID_CATEGORIES,
        logger=current_app.logger,
    )
    if not cards:
        flash("AI 未能生成可靠素材，请确认 Ollama 正在运行后重试。", "error")
        return redirect(url_for("drill.materials"))

    for item in cards:
        db.session.add(
            DrillPhrase(
                **item,
                source=source["label"][:100],
                source_type=source["type"],
                source_id=source["id"],
                status="pending",
                active=True,
            )
        )
    db.session.commit()
    flash(f"AI 已生成 {len(cards)} 条待审核素材。", "success")
    return redirect(url_for("drill.materials", status="pending"))


@drill_bp.route("/add", methods=["POST"])
def add():
    cn = (request.form.get("cn") or "").strip()
    en = (request.form.get("en") or "").strip()
    category = (request.form.get("category") or "meeting").strip()
    if not cn or not en:
        flash("中文意图和英文表达都需要填写。", "error")
        return redirect(url_for("drill.materials", status="approved"))
    if category not in VALID_CATEGORIES:
        category = "meeting"
    phrase = DrillPhrase(
        category=category,
        topic=(request.form.get("topic") or "").strip() or None,
        difficulty=(request.form.get("difficulty") or "intermediate").strip(),
        context_cn=(request.form.get("context_cn") or "").strip() or None,
        cn=cn,
        en=en,
        key_terms=(request.form.get("key_terms") or "").strip() or None,
        note=(request.form.get("note") or "").strip() or None,
        source=(request.form.get("source") or "").strip() or None,
        status="approved",
        active=True,
    )
    db.session.add(phrase)
    db.session.commit()
    flash("训练素材已添加。", "success")
    return redirect(url_for("drill.materials", status="approved"))


@drill_bp.route("/materials/<int:pid>/approve", methods=["POST"])
def approve(pid):
    phrase = DrillPhrase.query.get_or_404(pid)
    phrase.status = "approved"
    phrase.updated_at = datetime.utcnow()
    db.session.commit()
    flash("素材已批准并加入训练。", "success")
    return redirect(url_for("drill.materials", status="pending"))


@drill_bp.route("/materials/<int:pid>/edit", methods=["POST"])
def edit(pid):
    phrase = DrillPhrase.query.get_or_404(pid)
    category = (request.form.get("category") or phrase.category).strip()
    if category in VALID_CATEGORIES:
        phrase.category = category
    phrase.context_cn = (request.form.get("context_cn") or "").strip() or None
    phrase.cn = (request.form.get("cn") or "").strip() or phrase.cn
    phrase.en = (request.form.get("en") or "").strip() or phrase.en
    phrase.key_terms = (request.form.get("key_terms") or "").strip() or None
    phrase.note = (request.form.get("note") or "").strip() or None
    phrase.difficulty = (request.form.get("difficulty") or phrase.difficulty).strip()
    phrase.updated_at = datetime.utcnow()
    db.session.commit()
    flash("素材已更新。", "success")
    return redirect(url_for("drill.materials", status=request.args.get("status", "pending")))


@drill_bp.route("/delete/<int:pid>", methods=["POST"])
def delete(pid):
    phrase = DrillPhrase.query.get_or_404(pid)
    phrase.active = False
    phrase.status = "archived"
    phrase.updated_at = datetime.utcnow()
    db.session.commit()
    flash("素材已归档。", "success")
    return redirect(url_for("drill.materials", status=request.args.get("status", "pending")))


@drill_bp.route("/export")
def export():
    """Legacy offline export retained for compatibility, but no longer promoted."""
    category = request.args.get("category", "").strip()
    query = _approved_query()
    if category in VALID_CATEGORIES:
        query = query.filter(DrillPhrase.category == category)
    phrases = query.order_by(DrillPhrase.category, DrillPhrase.id).all()
    html = render_template(
        "drill/offline.html",
        phrases_json=json.dumps([phrase.to_dict() for phrase in phrases], ensure_ascii=False),
        cat_json=json.dumps(CATEGORY_CHOICES, ensure_ascii=False),
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        count=len(phrases),
    )
    return Response(
        html,
        mimetype="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="sqe_english_{datetime.now():%Y%m%d}.html"'
        },
    )
