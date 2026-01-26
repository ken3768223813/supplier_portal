from flask import render_template, request, redirect, url_for, flash
from sqlalchemy import or_, func
from datetime import datetime

from . import knowledge_bp
from ...extensions import db
from ...models import KnowledgeItem

# 工艺类型定义
PROCESSES = {
    'welding': {'name': '焊接', 'icon': '🔥', 'color': 'orange'},
    'coating': {'name': '涂装', 'icon': '🎨', 'color': 'blue'},
    'smt': {'name': 'SMT', 'icon': '⚡', 'color': 'green'},
    'molding': {'name': '注塑', 'icon': '🔧', 'color': 'purple'},
    'stamping': {'name': '冲压', 'icon': '⚙️', 'color': 'yellow'},
    'assembly': {'name': '组装', 'icon': '🔩', 'color': 'cyan'},
    'testing': {'name': '测试', 'icon': '🔬', 'color': 'pink'},
    'packaging': {'name': '包装', 'icon': '📦', 'color': 'indigo'},
    'other': {'name': '其他', 'icon': '📋', 'color': 'slate'},
}

CASE_TYPES = {
    'problem': '问题案例',
    'solution': '解决方案',
    'best_practice': '最佳实践',
    'tip': '经验技巧',
}

PRIORITIES = {
    'high': '重要',
    'normal': '普通',
    'low': '参考',
}


@knowledge_bp.route("/", methods=["GET"])
def index():
    """知识库主页"""
    search_query = request.args.get("q", "").strip()
    selected_process = request.args.get("process", "").strip()

    # 基础查询
    query = KnowledgeItem.query

    # 按工艺过滤
    if selected_process and selected_process in PROCESSES:
        query = query.filter_by(process=selected_process)

    # 搜索过滤
    if search_query:
        like = f"%{search_query}%"
        query = query.filter(
            or_(
                KnowledgeItem.title.ilike(like),
                KnowledgeItem.content.ilike(like),
                KnowledgeItem.tags.ilike(like),
                KnowledgeItem.supplier_name.ilike(like),
                KnowledgeItem.part_number.ilike(like),
            )
        )

    # 按创建时间倒序排列
    knowledge_items = query.order_by(KnowledgeItem.created_at.desc()).all()

    # 统计各工艺的知识数量
    processes_with_count = []
    for slug, info in PROCESSES.items():
        count = KnowledgeItem.query.filter_by(process=slug).count()
        processes_with_count.append({
            'slug': slug,
            'name': info['name'],
            'icon': info['icon'],
            'count': count,
        })

    # 处理知识条目数据
    for item in knowledge_items:
        item.process_name = PROCESSES.get(item.process, {}).get('name', item.process)

    # 总计数
    total_count = KnowledgeItem.query.count()

    # 获取选中工艺的名称
    selected_process_name = PROCESSES.get(selected_process, {}).get('name', '') if selected_process else None

    return render_template(
        "knowledge/index.html",
        knowledge_items=knowledge_items,
        processes=processes_with_count,
        selected_process=selected_process,
        selected_process_name=selected_process_name,
        search_query=search_query,
        total_count=total_count,
    )


@knowledge_bp.route("/item/<int:item_id>", methods=["GET"])
def view_item(item_id):
    """查看知识详情"""
    item = KnowledgeItem.query.get_or_404(item_id)

    item.process_name = PROCESSES.get(item.process, {}).get('name', item.process)
    item.case_type_name = CASE_TYPES.get(item.case_type, item.case_type) if item.case_type else None
    item.priority_name = PRIORITIES.get(item.priority, item.priority)

    # 查找相关知识
    related_items = KnowledgeItem.query.filter(
        KnowledgeItem.process == item.process,
        KnowledgeItem.id != item.id
    ).order_by(KnowledgeItem.created_at.desc()).limit(6).all()

    for related in related_items:
        related.process_name = PROCESSES.get(related.process, {}).get('name', related.process)

    return render_template(
        "knowledge/detail.html",
        item=item,
        related_items=related_items,
        processes=PROCESSES,
    )


@knowledge_bp.route("/quick-add", methods=["GET", "POST"])
def quick_add():
    """快速添加知识"""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        process = request.form.get("process", "").strip()
        priority = request.form.get("priority", "normal").strip()
        case_type = request.form.get("case_type", "").strip() or None
        supplier_name = request.form.get("supplier_name", "").strip() or None
        part_number = request.form.get("part_number", "").strip() or None
        tags_input = request.form.get("tags", "").strip()

        # 验证
        if not title:
            flash("❌ 标题不能为空", "error")
            return render_template("knowledge/quick_add.html",
                                 processes=PROCESSES,
                                 case_types=CASE_TYPES,
                                 priorities=PRIORITIES)

        if not content:
            flash("❌ 内容不能为空", "error")
            return render_template("knowledge/quick_add.html",
                                 processes=PROCESSES,
                                 case_types=CASE_TYPES,
                                 priorities=PRIORITIES)

        if not process or process not in PROCESSES:
            flash("❌ 请选择有效的工艺类型", "error")
            return render_template("knowledge/quick_add.html",
                                 processes=PROCESSES,
                                 case_types=CASE_TYPES,
                                 priorities=PRIORITIES)

        # 创建知识条目
        item = KnowledgeItem(
            title=title,
            content=content,
            process=process,
            priority=priority,
            case_type=case_type,
            supplier_name=supplier_name,
            part_number=part_number,
        )

        # 处理标签
        if tags_input:
            tags_list = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
            item.tags = ','.join(tags_list)

        db.session.add(item)
        db.session.commit()

        flash(f"✅ 知识已记录：{title}", "success")
        return redirect(url_for("knowledge.view_item", item_id=item.id))

    return render_template("knowledge/quick_add.html",
                         processes=PROCESSES,
                         case_types=CASE_TYPES,
                         priorities=PRIORITIES)


@knowledge_bp.route("/item/<int:item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id):
    """编辑知识"""
    item = KnowledgeItem.query.get_or_404(item_id)

    if request.method == "POST":
        item.title = request.form.get("title", "").strip()
        item.content = request.form.get("content", "").strip()
        item.process = request.form.get("process", "").strip()
        item.priority = request.form.get("priority", "normal").strip()
        item.case_type = request.form.get("case_type", "").strip() or None
        item.supplier_name = request.form.get("supplier_name", "").strip() or None
        item.part_number = request.form.get("part_number", "").strip() or None

        tags_input = request.form.get("tags", "").strip()
        if tags_input:
            tags_list = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
            item.tags = ','.join(tags_list)
        else:
            item.tags = None

        if not item.title or not item.content:
            flash("❌ 标题和内容不能为空", "error")
        elif not item.process or item.process not in PROCESSES:
            flash("❌ 请选择有效的工艺类型", "error")
        else:
            db.session.commit()
            flash("✅ 知识已更新", "success")
            return redirect(url_for("knowledge.view_item", item_id=item.id))

    # GET 请求
    tags_list = item.get_tags_list()
    item.tags_display = ','.join(tags_list) if tags_list else ''

    return render_template("knowledge/edit.html",
                         item=item,
                         processes=PROCESSES,
                         case_types=CASE_TYPES,
                         priorities=PRIORITIES)


@knowledge_bp.route("/item/<int:item_id>/delete", methods=["POST"])
def delete_item(item_id):
    """删除知识"""
    item = KnowledgeItem.query.get_or_404(item_id)

    title = item.title
    db.session.delete(item)
    db.session.commit()

    flash(f"✅ 已删除知识：{title}", "success")
    return redirect(url_for("knowledge.index"))