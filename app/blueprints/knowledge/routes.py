# app/blueprints/knowledge/routes.py
"""
Knowledge Base 路由 + 思维导图 API
"""
from flask import render_template, request, redirect, url_for, flash, jsonify, abort
from sqlalchemy import or_
from datetime import datetime

from . import knowledge_bp
from ...extensions import db
from ...models import KnowledgeItem, FileLibrary, NodeStandard, NodeKnowledgeLink
from .mindmap_data import PROCESS_META, get_mindmap, get_node

# ─────────────────────────────────────────────
#  工艺类型定义（与 mindmap_data 保持一致）
# ─────────────────────────────────────────────
PROCESSES = {
    "casting":  {"name": "铸造工艺", "icon": "🏭", "color": "#3b82f6"},
    "welding":  {"name": "焊接工艺", "icon": "🔥", "color": "#f59e0b"},
    "coating":  {"name": "涂装工艺", "icon": "🎨", "color": "#10b981"},
    "smt":      {"name": "SMT工艺",  "icon": "⚡", "color": "#8b5cf6"},
    "molding":  {"name": "注塑工艺", "icon": "🔧", "color": "#ec4899"},
    "stamping": {"name": "冲压工艺", "icon": "⚙️", "color": "#06b6d4"},
    "assembly": {"name": "组装工艺", "icon": "🔩", "color": "#84cc16"},
    "testing":  {"name": "测试工艺", "icon": "🔬", "color": "#f43f5e"},
    "other":    {"name": "其他",     "icon": "📋", "color": "#6b7280"},
}

CASE_TYPES = {
    "problem":       "问题案例",
    "solution":      "解决方案",
    "best_practice": "最佳实践",
    "tip":           "经验技巧",
}

PRIORITIES = {
    "high":   "重要",
    "normal": "普通",
    "low":    "参考",
}


# ══════════════════════════════════════════════════════════════════════
#  主页面
# ══════════════════════════════════════════════════════════════════════

@knowledge_bp.route("/", methods=["GET"])
def index():
    """知识库主页（含思维导图入口）"""
    search_query     = request.args.get("q", "").strip()
    selected_process = request.args.get("process", "casting").strip()
    view_mode        = request.args.get("view", "mindmap")   # mindmap | cards

    # 基础查询
    query = KnowledgeItem.query
    if selected_process and selected_process in PROCESSES:
        query = query.filter_by(process=selected_process)
    if search_query:
        like = f"%{search_query}%"
        query = query.filter(
            or_(
                KnowledgeItem.title.ilike(like),
                KnowledgeItem.content.ilike(like),
                KnowledgeItem.tags.ilike(like),
            )
        )
    knowledge_items = query.order_by(KnowledgeItem.created_at.desc()).all()

    # 统计各工艺数量
    processes_with_count = []
    for slug, info in PROCESSES.items():
        count = KnowledgeItem.query.filter_by(process=slug).count()
        processes_with_count.append({
            "slug":  slug,
            "name":  info["name"],
            "icon":  info["icon"],
            "color": info["color"],
            "count": count,
        })

    for item in knowledge_items:
        item.process_name = PROCESSES.get(item.process, {}).get("name", item.process)

    total_count = KnowledgeItem.query.count()

    # 侧边栏关联标准（当前工艺下 node=root 的 NodeStandard）
    sidebar_stds = (
        NodeStandard.query
        .filter_by(process=selected_process, node_id="root")
        .order_by(NodeStandard.created_at.asc())
        .all()
    )

    return render_template(
        "knowledge/index.html",
        knowledge_items=knowledge_items,
        processes=processes_with_count,
        selected_process=selected_process,
        selected_process_name=PROCESSES.get(selected_process, {}).get("name", ""),
        search_query=search_query,
        total_count=total_count,
        view_mode=view_mode,
        sidebar_stds=sidebar_stds,
        process_meta=PROCESS_META,
    )


# ══════════════════════════════════════════════════════════════════════
#  知识条目 CRUD
# ══════════════════════════════════════════════════════════════════════

@knowledge_bp.route("/item/<int:item_id>", methods=["GET"])
def view_item(item_id):
    item = KnowledgeItem.query.get_or_404(item_id)
    item.process_name  = PROCESSES.get(item.process, {}).get("name", item.process)
    item.case_type_name= CASE_TYPES.get(item.case_type, item.case_type) if item.case_type else None
    item.priority_name = PRIORITIES.get(item.priority, item.priority)

    related_items = (
        KnowledgeItem.query
        .filter(KnowledgeItem.process == item.process, KnowledgeItem.id != item.id)
        .order_by(KnowledgeItem.created_at.desc())
        .limit(6)
        .all()
    )
    for r in related_items:
        r.process_name = PROCESSES.get(r.process, {}).get("name", r.process)

    # 已绑定此条目的节点
    node_links = NodeKnowledgeLink.query.filter_by(knowledge_id=item_id).all()

    return render_template(
        "knowledge/detail.html",
        item=item,
        related_items=related_items,
        processes=PROCESSES,
        node_links=node_links,
    )


@knowledge_bp.route("/quick-add", methods=["GET", "POST"])
def quick_add():
    if request.method == "POST":
        title    = request.form.get("title", "").strip()
        content  = request.form.get("content", "").strip()
        process  = request.form.get("process", "").strip()
        priority = request.form.get("priority", "normal").strip()
        case_type     = request.form.get("case_type", "").strip() or None
        supplier_name = request.form.get("supplier_name", "").strip() or None
        part_number   = request.form.get("part_number", "").strip() or None
        tags_input    = request.form.get("tags", "").strip()

        # 从 mindmap 页面携带的 node 绑定参数
        bind_process = request.form.get("bind_process", "").strip()
        bind_node_id = request.form.get("bind_node_id", "").strip()

        if not title:
            flash("❌ 标题不能为空", "error")
            return render_template("knowledge/quick_add.html",
                                   processes=PROCESSES, case_types=CASE_TYPES, priorities=PRIORITIES)
        if not content:
            flash("❌ 内容不能为空", "error")
            return render_template("knowledge/quick_add.html",
                                   processes=PROCESSES, case_types=CASE_TYPES, priorities=PRIORITIES)
        if not process or process not in PROCESSES:
            flash("❌ 请选择有效的工艺类型", "error")
            return render_template("knowledge/quick_add.html",
                                   processes=PROCESSES, case_types=CASE_TYPES, priorities=PRIORITIES)

        item = KnowledgeItem(
            title=title, content=content, process=process,
            priority=priority, case_type=case_type,
            supplier_name=supplier_name, part_number=part_number,
        )
        if tags_input:
            item.tags = ",".join(t.strip() for t in tags_input.split(",") if t.strip())

        db.session.add(item)
        db.session.flush()   # 获取 item.id

        # 自动绑定到思维导图节点
        if bind_process and bind_node_id:
            link = NodeKnowledgeLink(
                process=bind_process, node_id=bind_node_id, knowledge_id=item.id
            )
            db.session.add(link)

        db.session.commit()
        flash(f"✅ 知识已记录：{title}", "success")
        return redirect(url_for("knowledge.view_item", item_id=item.id))

    return render_template("knowledge/quick_add.html",
                           processes=PROCESSES, case_types=CASE_TYPES, priorities=PRIORITIES)


@knowledge_bp.route("/item/<int:item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id):
    item = KnowledgeItem.query.get_or_404(item_id)
    if request.method == "POST":
        item.title        = request.form.get("title", "").strip()
        item.content      = request.form.get("content", "").strip()
        item.process      = request.form.get("process", "").strip()
        item.priority     = request.form.get("priority", "normal").strip()
        item.case_type    = request.form.get("case_type", "").strip() or None
        item.supplier_name= request.form.get("supplier_name", "").strip() or None
        item.part_number  = request.form.get("part_number", "").strip() or None
        tags_input        = request.form.get("tags", "").strip()
        item.tags = ",".join(t.strip() for t in tags_input.split(",") if t.strip()) if tags_input else None

        if not item.title or not item.content:
            flash("❌ 标题和内容不能为空", "error")
        elif not item.process or item.process not in PROCESSES:
            flash("❌ 请选择有效的工艺类型", "error")
        else:
            db.session.commit()
            flash("✅ 知识已更新", "success")
            return redirect(url_for("knowledge.view_item", item_id=item.id))

    tags_list = item.get_tags_list()
    item.tags_display = ",".join(tags_list) if tags_list else ""
    return render_template("knowledge/edit.html", item=item,
                           processes=PROCESSES, case_types=CASE_TYPES, priorities=PRIORITIES)


@knowledge_bp.route("/item/<int:item_id>/delete", methods=["POST"])
def delete_item(item_id):
    item = KnowledgeItem.query.get_or_404(item_id)
    title = item.title
    db.session.delete(item)
    db.session.commit()
    flash(f"✅ 已删除知识：{title}", "success")
    return redirect(url_for("knowledge.index"))


# ══════════════════════════════════════════════════════════════════════
#  思维导图 API
# ══════════════════════════════════════════════════════════════════════

@knowledge_bp.route("/api/mindmap/<process>", methods=["GET"])
def api_mindmap(process):
    """返回指定工艺的思维导图节点（含 DB 中用户自定义关联）"""
    if process not in PROCESSES:
        return jsonify({"error": "未知工艺"}), 404

    nodes = get_mindmap(process)
    if not nodes:
        return jsonify({"nodes": [], "meta": PROCESS_META.get(process, {})})

    return jsonify({
        "nodes": nodes,
        "meta":  PROCESS_META.get(process, {}),
    })


@knowledge_bp.route("/api/node/<process>/<node_id>", methods=["GET"])
def api_node_detail(process, node_id):
    """返回单个节点的完整详情，含 DB 中绑定的标准和知识条目"""
    node = get_node(process, node_id)
    if not node:
        return jsonify({"error": "节点不存在"}), 404

    # 从 DB 读取用户关联的标准
    db_stds = (
        NodeStandard.query
        .filter_by(process=process, node_id=node_id)
        .order_by(NodeStandard.created_at.asc())
        .all()
    )

    # 从 DB 读取绑定的知识条目
    db_links = (
        NodeKnowledgeLink.query
        .filter_by(process=process, node_id=node_id)
        .order_by(NodeKnowledgeLink.created_at.desc())
        .all()
    )

    return jsonify({
        "node":       node,
        "db_stds":    [s.to_dict() for s in db_stds],
        "db_links":   [lk.to_dict() for lk in db_links],
    })


# ── 关联标准 CRUD ──────────────────────────────

@knowledge_bp.route("/api/node-standard", methods=["POST"])
def api_add_node_standard():
    """为思维导图节点关联一条标准（自定义或来自 FileLibrary）"""
    data = request.get_json(silent=True) or {}
    process  = data.get("process", "").strip()
    node_id  = data.get("node_id", "").strip()
    std_code = data.get("std_code", "").strip()
    std_name = data.get("std_name", "").strip()
    std_type = data.get("std_type", "").strip()
    std_link = data.get("std_link", "").strip() or None
    file_id  = data.get("file_id")
    remark   = data.get("remark", "").strip() or None

    if not process or not node_id:
        return jsonify({"error": "process 和 node_id 不能为空"}), 400
    if not std_code and not file_id:
        return jsonify({"error": "std_code 或 file_id 至少填一项"}), 400
    if process not in PROCESSES:
        return jsonify({"error": "未知工艺"}), 400

    # 验证 file_id
    if file_id:
        file = FileLibrary.query.get(file_id)
        if not file:
            return jsonify({"error": "文件不存在"}), 404

    ns = NodeStandard(
        process=process, node_id=node_id,
        std_code=std_code or None,
        std_name=std_name or None,
        std_type=std_type or None,
        std_link=std_link,
        file_id=file_id or None,
        remark=remark,
    )
    db.session.add(ns)
    db.session.commit()
    return jsonify({"success": True, "id": ns.id, "data": ns.to_dict()}), 201


@knowledge_bp.route("/api/node-standard/<int:std_id>", methods=["DELETE"])
def api_delete_node_standard(std_id):
    """删除节点关联的标准"""
    ns = NodeStandard.query.get_or_404(std_id)
    db.session.delete(ns)
    db.session.commit()
    return jsonify({"success": True})


# ── 关联知识条目 CRUD ─────────────────────────

@knowledge_bp.route("/api/node-knowledge", methods=["POST"])
def api_add_node_knowledge():
    """为思维导图节点关联一条知识条目"""
    data         = request.get_json(silent=True) or {}
    process      = data.get("process", "").strip()
    node_id      = data.get("node_id", "").strip()
    knowledge_id = data.get("knowledge_id")

    if not process or not node_id or not knowledge_id:
        return jsonify({"error": "process / node_id / knowledge_id 均不能为空"}), 400

    ki = KnowledgeItem.query.get(knowledge_id)
    if not ki:
        return jsonify({"error": "知识条目不存在"}), 404

    # 防止重复
    exists = NodeKnowledgeLink.query.filter_by(
        process=process, node_id=node_id, knowledge_id=knowledge_id
    ).first()
    if exists:
        return jsonify({"error": "已关联"}), 409

    link = NodeKnowledgeLink(process=process, node_id=node_id, knowledge_id=knowledge_id)
    db.session.add(link)
    db.session.commit()
    return jsonify({"success": True, "id": link.id, "data": link.to_dict()}), 201


@knowledge_bp.route("/api/node-knowledge/<int:link_id>", methods=["DELETE"])
def api_delete_node_knowledge(link_id):
    """删除节点关联的知识条目"""
    link = NodeKnowledgeLink.query.get_or_404(link_id)
    db.session.delete(link)
    db.session.commit()
    return jsonify({"success": True})


# ── 文件库搜索（供关联标准弹窗使用）──────────

@knowledge_bp.route("/api/files/search", methods=["GET"])
def api_search_files():
    """搜索 FileLibrary 供关联标准使用"""
    q = request.args.get("q", "").strip()
    process = request.args.get("process", "").strip()
    base = FileLibrary.query
    if process:
        base = base.filter_by(related_process=process)
    if q:
        like = f"%{q}%"
        base = base.filter(
            or_(FileLibrary.title.ilike(like), FileLibrary.tags.ilike(like),
                FileLibrary.description.ilike(like))
        )
    files = base.order_by(FileLibrary.created_at.desc()).limit(20).all()
    return jsonify([
        {"id": f.id, "title": f.title, "category": f.category,
         "version": f.version, "tags": f.get_tags_list()}
        for f in files
    ])


# ── 知识条目搜索（供关联知识弹窗使用）──────────

@knowledge_bp.route("/api/knowledge/search", methods=["GET"])
def api_search_knowledge():
    """搜索 KnowledgeItem 供节点绑定使用"""
    q       = request.args.get("q", "").strip()
    process = request.args.get("process", "").strip()
    base    = KnowledgeItem.query
    if process:
        base = base.filter_by(process=process)
    if q:
        like = f"%{q}%"
        base = base.filter(
            or_(KnowledgeItem.title.ilike(like), KnowledgeItem.content.ilike(like))
        )
    items = base.order_by(KnowledgeItem.created_at.desc()).limit(20).all()
    return jsonify([
        {"id": i.id, "title": i.title, "process": i.process,
         "priority": i.priority, "case_type": i.case_type}
        for i in items
    ])