"""
Tasks Routes
任务管理路由
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from sqlalchemy import or_, and_
from datetime import datetime, date, timedelta

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')

from . import tasks_bp
from ...extensions import db
from ...models import Task, TaskUpdate, TaskAttachment, Supplier


def generate_task_no():
    """生成任务编号：TASK-YYYY-XXX"""
    current_year = datetime.now().year

    last_task = Task.query.filter(
        Task.task_no.like(f"TASK-{current_year}-%")
    ).order_by(Task.task_no.desc()).first()

    if last_task:
        try:
            last_num = int(last_task.task_no.split("-")[-1])
            new_num = last_num + 1
        except (ValueError, IndexError):
            new_num = 1
    else:
        new_num = 1

    return f"TASK-{current_year}-{new_num:03d}"


@tasks_bp.route('/', methods=['GET'])
def index():
    """任务列表页（看板视图）"""
    # 获取筛选参数
    priority_filter = request.args.get('priority')
    category_filter = request.args.get('category')

    query = Task.query

    # 应用筛选
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
    if category_filter:
        query = query.filter_by(category=category_filter)

    # 获取所有任务
    all_tasks = query.order_by(
        Task.due_date.asc().nullslast(),
        Task.priority.desc(),
        Task.created_at.desc()
    ).all()

    # 按状态分组
    tasks_by_status = {
        'pending': [],
        'in_progress': [],
        'on_hold': [],
        'completed': []
    }

    for task in all_tasks:
        if task.status in tasks_by_status:
            tasks_by_status[task.status].append(task)

    # 统计数据
    today = date.today()

    stats = {
        'total': Task.query.count(),
        'urgent': Task.query.filter_by(priority='urgent').filter(
            Task.status.in_(['pending', 'in_progress'])
        ).count(),
        'in_progress': Task.query.filter_by(status='in_progress').count(),
        'due_today': Task.query.filter(
            Task.due_date == today,
            Task.status.in_(['pending', 'in_progress'])
        ).count(),
        'overdue': Task.query.filter(
            Task.due_date < today,
            Task.status.in_(['pending', 'in_progress'])
        ).count()
    }

    return render_template(
        'tasks/index.html',
        tasks_by_status=tasks_by_status,
        all_tasks=all_tasks,
        stats=stats
    )


@tasks_bp.route('/new', methods=['GET', 'POST'])
def new_task():
    """新建任务"""
    if request.method == 'POST':
        # 获取表单数据
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip() or None
        source = (request.form.get('source') or '').strip()
        category = (request.form.get('category') or '').strip() or None
        requester = (request.form.get('requester') or '').strip() or None
        source_reference = (request.form.get('source_reference') or '').strip() or None

        priority = (request.form.get('priority') or 'medium').strip()

        start_date_str = (request.form.get('start_date') or '').strip()
        due_date_str = (request.form.get('due_date') or '').strip()

        related_supplier = (request.form.get('related_supplier') or '').strip() or None
        related_tr_no = (request.form.get('related_tr_no') or '').strip() or None
        related_audit_no = (request.form.get('related_audit_no') or '').strip() or None
        related_trip_no = (request.form.get('related_trip_no') or '').strip() or None

        notes = (request.form.get('notes') or '').strip() or None

        # 验证必填字段
        if not title:
            flash('Task title is required', 'error')
            return redirect(request.url)

        if not source:
            flash('Task source is required', 'error')
            return redirect(request.url)

        if not due_date_str:
            flash('Due date is required', 'error')
            return redirect(request.url)

        # 解析日期
        start_date = None
        due_date = None

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid start date format', 'error')
                return redirect(request.url)

        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid due date format', 'error')
            return redirect(request.url)

        # 生成任务编号
        task_no = generate_task_no()

        # 创建任务
        task = Task(
            task_no=task_no,
            title=title,
            description=description,
            source=source,
            source_reference=source_reference,
            requester=requester,
            category=category,
            priority=priority,
            due_date=due_date,
            start_date=start_date,
            status='pending',
            related_supplier=related_supplier,
            related_tr_no=related_tr_no,
            related_audit_no=related_audit_no,
            related_trip_no=related_trip_no,
            notes=notes
        )

        db.session.add(task)
        db.session.commit()

        flash(f'✅ Task created successfully: {task_no}', 'success')
        return redirect(url_for('tasks.task_detail', task_id=task.id))

    # GET - 显示表单
    suppliers = Supplier.query.order_by(Supplier.code).all()
    return render_template('tasks/new.html', suppliers=suppliers)


@tasks_bp.route('/<int:task_id>', methods=['GET'])
def task_detail(task_id):
    """任务详情页"""
    task = Task.query.get_or_404(task_id)

    # 获取进展更新
    updates = task.updates.all()

    # 获取附件
    attachments = task.attachments.all()

    return render_template(
        'tasks/detail.html',
        task=task,
        updates=updates,
        attachments=attachments
    )


@tasks_bp.route('/<int:task_id>/update', methods=['POST'])
def update_task(task_id):
    """更新任务"""
    task = Task.query.get_or_404(task_id)

    old_status = task.status
    old_progress = task.progress

    # 更新字段
    task.title = (request.form.get('title') or '').strip()
    task.description = (request.form.get('description') or '').strip() or None
    task.priority = (request.form.get('priority') or 'medium').strip()
    task.status = (request.form.get('status') or 'pending').strip()
    task.progress = int(request.form.get('progress', 0))
    task.notes = (request.form.get('notes') or '').strip() or None

    # 更新日期
    due_date_str = (request.form.get('due_date') or '').strip()
    if due_date_str:
        try:
            task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # 如果状态改为 completed，记录完成日期
    if task.status == 'completed' and old_status != 'completed':
        task.completed_date = date.today()
        task.progress = 100

    # 记录进展更新
    comment = (request.form.get('comment') or '').strip()
    if comment or old_status != task.status or old_progress != task.progress:
        update = TaskUpdate(
            task_id=task.id,
            update_type='status_change' if old_status != task.status else 'progress_update',
            old_status=old_status,
            new_status=task.status,
            old_progress=old_progress,
            new_progress=task.progress,
            content=comment,
            updated_by='Current User'  # 可以改为实际登录用户
        )
        db.session.add(update)

    db.session.commit()

    flash('✅ Task updated successfully', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task.id))


@tasks_bp.route('/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    """删除任务"""
    task = Task.query.get_or_404(task_id)

    db.session.delete(task)
    db.session.commit()

    flash('✅ Task deleted successfully', 'success')
    return redirect(url_for('tasks.index'))


@tasks_bp.route('/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    """快速标记任务为完成"""
    task = Task.query.get_or_404(task_id)

    old_status = task.status
    task.status = 'completed'
    task.completed_date = date.today()
    task.progress = 100

    # 记录状态变更
    update = TaskUpdate(
        task_id=task.id,
        update_type='status_change',
        old_status=old_status,
        new_status='completed',
        old_progress=task.progress,
        new_progress=100,
        content='Task marked as completed',
        updated_by='Current User'
    )
    db.session.add(update)
    db.session.commit()

    flash('✅ Task marked as completed', 'success')
    return redirect(url_for('tasks.index'))