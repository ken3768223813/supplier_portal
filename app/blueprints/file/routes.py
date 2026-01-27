from flask import (
    render_template, request, redirect, url_for, flash,
    current_app, send_file, abort, Response
)
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from datetime import datetime
import os
import uuid
import sys
import subprocess

from . import file_bp
from ...extensions import db
from ...models import FileLibrary


# 文件分类定义
CATEGORIES = {
    'standard': {'name': '标准文件', 'icon': '📋', 'color': 'blue'},
    'checklist': {'name': '检查表', 'icon': '✓', 'color': 'green'},
    'specification': {'name': '规范文件', 'icon': '📐', 'color': 'purple'},
    'template': {'name': '模板文件', 'icon': '📄', 'color': 'orange'},
    'procedure': {'name': '程序文件', 'icon': '📑', 'color': 'indigo'},
    'manual': {'name': '手册', 'icon': '📚', 'color': 'cyan'},
    'other': {'name': '其他', 'icon': '📎', 'color': 'slate'},
}

ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'jpg', 'jpeg', 'png', 'zip', 'rar'
}


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _open_file_on_host(path: str) -> bool:
    """在运行 Flask 的这台电脑上，用系统默认程序打开文件（本机单人使用场景）"""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform.startswith("darwin"):
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


@file_bp.route("/", methods=["GET"])
def index():
    """文件库主页"""
    search_query = request.args.get("q", "").strip()
    selected_category = request.args.get("category", "").strip()

    # 基础查询
    query = FileLibrary.query

    # 按分类过滤
    if selected_category and selected_category in CATEGORIES:
        query = query.filter_by(category=selected_category)

    # 搜索过滤
    if search_query:
        like = f"%{search_query}%"
        query = query.filter(
            or_(
                FileLibrary.title.ilike(like),
                FileLibrary.description.ilike(like),
                FileLibrary.tags.ilike(like),
                FileLibrary.original_name.ilike(like),
                FileLibrary.supplier_name.ilike(like),
            )
        )

    # 按创建时间倒序
    files = query.order_by(FileLibrary.created_at.desc()).all()

    # 统计各分类的文件数量
    categories_with_count = []
    for slug, info in CATEGORIES.items():
        count = FileLibrary.query.filter_by(category=slug).count()
        categories_with_count.append({
            'slug': slug,
            'name': info['name'],
            'icon': info['icon'],
            'count': count,
        })

    # 处理文件数据（给模板用的展示字段）
    for f in files:
        f.category_name = CATEGORIES.get(f.category, {}).get('name', f.category)

    # 总计数
    total_count = FileLibrary.query.count()

    # 获取选中分类的名称
    selected_category_name = CATEGORIES.get(selected_category, {}).get('name', '') if selected_category else None

    return render_template(
        "file/index.html",
        files=files,
        categories=categories_with_count,
        selected_category=selected_category,
        selected_category_name=selected_category_name,
        search_query=search_query,
        total_count=total_count,
    )


@file_bp.route("/upload", methods=["GET", "POST"])
def upload():
    """上传文件"""
    if request.method == "POST":
        # 检查文件
        if 'file' not in request.files:
            flash("❌ 未选择文件", "error")
            return redirect(url_for("file.upload"))

        file = request.files['file']
        if not file or file.filename == '':
            flash("❌ 未选择文件", "error")
            return redirect(url_for("file.upload"))

        if not allowed_file(file.filename):
            flash(f"❌ 不支持的文件格式。允许的格式：{', '.join(sorted(ALLOWED_EXTENSIONS))}", "error")
            return redirect(url_for("file.upload"))

        # 获取表单数据
        title = request.form.get("title", "").strip() or file.filename
        description = request.form.get("description", "").strip() or None
        category = request.form.get("category", "other").strip()
        version = request.form.get("version", "").strip() or None
        issue_date_str = request.form.get("issue_date", "").strip()
        tags_input = request.form.get("tags", "").strip()
        related_process = request.form.get("related_process", "").strip() or None
        supplier_name = request.form.get("supplier_name", "").strip() or None
        part_category = request.form.get("part_category", "").strip() or None

        # 验证分类
        if category not in CATEGORIES:
            flash("❌ 请选择有效的文件分类", "error")
            return redirect(url_for("file.upload"))

        # 处理日期
        issue_date = None
        if issue_date_str:
            try:
                issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
            except ValueError:
                issue_date = None

        # 文件处理
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if not ext:
            flash("❌ 无法识别文件扩展名", "error")
            return redirect(url_for("file.upload"))

        stored_name = f"{uuid.uuid4().hex}.{ext}"

        # 存储路径：uploads/file_library/CATEGORY/
        category_dir = os.path.join("file_library", category)
        full_dir = os.path.join(current_app.config["UPLOAD_DIR"], category_dir)
        os.makedirs(full_dir, exist_ok=True)

        file_path = os.path.join(full_dir, stored_name)
        file.save(file_path)

        # 创建文件记录
        file_record = FileLibrary(
            title=title,
            description=description,
            category=category,
            original_name=filename,
            stored_name=stored_name,
            rel_path=os.path.join(category_dir, stored_name),
            mime=file.mimetype,
            size=os.path.getsize(file_path),
            version=version,
            issue_date=issue_date,
            related_process=related_process,
            supplier_name=supplier_name,
            part_category=part_category,
        )

        # 处理标签
        if tags_input:
            tags_list = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
            file_record.tags = ','.join(tags_list)

        db.session.add(file_record)
        db.session.commit()

        flash(f"✅ 文件已上传：{title}", "success")
        return redirect(url_for("file.index"))

    return render_template("file/upload.html", categories=CATEGORIES)


@file_bp.route("/<int:file_id>/view")
def view_file(file_id):
    """预览文件（浏览器内联打开）"""
    file_record = FileLibrary.query.get_or_404(file_id)

    # 增加查看次数
    file_record.view_count += 1
    db.session.commit()

    file_path = os.path.join(current_app.config["UPLOAD_DIR"], file_record.rel_path)
    if not os.path.exists(file_path):
        abort(404, "文件不存在")

    with open(file_path, 'rb') as f:
        file_data = f.read()

    response = Response(file_data, mimetype=file_record.mime or 'application/octet-stream')
    response.headers['Content-Disposition'] = f'inline; filename="{file_record.original_name}"'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@file_bp.route("/<int:file_id>/download")
def download_file(file_id):
    """下载文件（本地系统可不用，但保留路由）"""
    file_record = FileLibrary.query.get_or_404(file_id)

    # 增加下载次数
    file_record.download_count += 1
    db.session.commit()

    file_path = os.path.join(current_app.config["UPLOAD_DIR"], file_record.rel_path)
    if not os.path.exists(file_path):
        abort(404, "文件不存在")

    return send_file(
        file_path,
        as_attachment=True,
        download_name=file_record.original_name,
        mimetype=file_record.mime,
    )


@file_bp.route("/<int:file_id>/open", methods=["POST"])
def open_local(file_id):
    """本地打开文件（在服务器本机弹出默认程序）"""
    file_record = FileLibrary.query.get_or_404(file_id)

    file_path = os.path.join(current_app.config["UPLOAD_DIR"], file_record.rel_path)
    if not os.path.exists(file_path):
        abort(404, "文件不存在")

    ok = _open_file_on_host(file_path)
    if ok:
        flash(f"✅ 已在本机打开：{file_record.title}", "success")
    else:
        flash("❌ 打开失败（系统权限/路径/默认程序异常）", "error")

    # 回到列表页，并尽量保留查询参数
    q = request.args.get("q", "")
    category = request.args.get("category", "")
    return redirect(url_for("file.index", q=q, category=category))


@file_bp.route("/<int:file_id>/edit", methods=["GET", "POST"])
def edit_file(file_id):
    """编辑文件信息（删除功能在编辑页）"""
    file_record = FileLibrary.query.get_or_404(file_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip() or file_record.original_name
        description = request.form.get("description", "").strip() or None
        category = request.form.get("category", "other").strip()
        version = request.form.get("version", "").strip() or None
        issue_date_str = request.form.get("issue_date", "").strip()
        tags_input = request.form.get("tags", "").strip()
        related_process = request.form.get("related_process", "").strip() or None
        supplier_name = request.form.get("supplier_name", "").strip() or None
        part_category = request.form.get("part_category", "").strip() or None

        if category not in CATEGORIES:
            flash("❌ 请选择有效的文件分类", "error")
            return redirect(url_for("file.edit_file", file_id=file_id))

        issue_date = None
        if issue_date_str:
            try:
                issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
            except ValueError:
                issue_date = None

        file_record.title = title
        file_record.description = description
        file_record.category = category
        file_record.version = version
        file_record.issue_date = issue_date
        file_record.related_process = related_process
        file_record.supplier_name = supplier_name
        file_record.part_category = part_category

        if tags_input:
            tags_list = [t.strip() for t in tags_input.split(",") if t.strip()]
            file_record.tags = ",".join(tags_list)
        else:
            file_record.tags = None

        db.session.commit()
        flash("✅ 已更新文件信息", "success")
        return redirect(url_for("file.index"))

    return render_template("file/edit.html", file=file_record, categories=CATEGORIES)


@file_bp.route("/<int:file_id>/delete", methods=["POST"])
def delete_file(file_id):
    """删除文件（入口放在编辑页）"""
    file_record = FileLibrary.query.get_or_404(file_id)

    # 删除物理文件
    file_path = os.path.join(current_app.config["UPLOAD_DIR"], file_record.rel_path)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    title = file_record.title
    db.session.delete(file_record)
    db.session.commit()

    flash(f"✅ 已删除文件：{title}", "success")
    return redirect(url_for("file.index"))
