from flask import render_template, request
from datetime import datetime, timedelta
from sqlalchemy import func

from . import main_bp
from ...extensions import db
from ...models import Supplier, TroubleReport, BusinessTrip, KnowledgeItem, FileLibrary


@main_bp.route("/")
def index():
    """首页 Dashboard"""

    # 当前日期和星期
    current_date = datetime.now()
    weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    weekday = weekdays[current_date.weekday()]

    # 统计数据
    stats = {
        # 总数统计
        'suppliers': Supplier.query.count(),
        'tr_total': TroubleReport.query.count(),
        'tr_pending': TroubleReport.query.filter(
            TroubleReport.status.in_(['open', 'in_progress'])
        ).count(),
        'trip_total': BusinessTrip.query.count(),
        'trip_ongoing': BusinessTrip.query.filter_by(status='ongoing').count(),
        'knowledge': KnowledgeItem.query.count(),
        'file': FileLibrary.query.count(),

        # 本周统计（从周一开始）
        'week_tr': 0,
        'week_trip': 0,
        'week_knowledge': 0,
        'week_file': 0,
    }

    # 计算本周一的日期
    days_since_monday = current_date.weekday()
    week_start = current_date - timedelta(days=days_since_monday)
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    # 本周新增统计
    stats['week_tr'] = TroubleReport.query.filter(
        TroubleReport.created_at >= week_start
    ).count()

    stats['week_trip'] = BusinessTrip.query.filter(
        BusinessTrip.created_at >= week_start
    ).count()

    stats['week_knowledge'] = KnowledgeItem.query.filter(
        KnowledgeItem.created_at >= week_start
    ).count()

    stats['week_file'] = FileLibrary.query.filter(
        FileLibrary.created_at >= week_start
    ).count()

    # 最近活动（混合显示最近的 TR、出差、知识、文件）
    recent_activities = []

    # 获取最近的 TR
    recent_trs = TroubleReport.query.order_by(
        TroubleReport.created_at.desc()
    ).limit(3).all()

    for tr in recent_trs:
        time_ago = get_time_ago(tr.created_at)
        recent_activities.append({
            'type': 'tr',
            'type_name': '8D报告',
            'title': f"TR-{tr.tr_no}",
            'description': f"{tr.supplier_code} - {tr.issue_description[:50]}..." if len(
                tr.issue_description) > 50 else tr.issue_description,
            'url': f"/tr/{tr.id}",
            'time_ago': time_ago,
            'created_at': tr.created_at,
            'icon': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>',
        })

    # 获取最近的出差
    recent_trips = BusinessTrip.query.order_by(
        BusinessTrip.created_at.desc()
    ).limit(3).all()

    for trip in recent_trips:
        time_ago = get_time_ago(trip.created_at)
        recent_activities.append({
            'type': 'trip',
            'type_name': '出差',
            'title': trip.trip_no,
            'description': f"{trip.supplier_name} - {trip.purpose[:40]}..." if len(trip.purpose) > 40 else trip.purpose,
            'url': f"/trip/{trip.id}/edit",
            'time_ago': time_ago,
            'created_at': trip.created_at,
            'icon': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>',
        })

    # 获取最近的知识
    recent_knowledge = KnowledgeItem.query.order_by(
        KnowledgeItem.created_at.desc()
    ).limit(3).all()

    for item in recent_knowledge:
        time_ago = get_time_ago(item.created_at)
        recent_activities.append({
            'type': 'knowledge',
            'type_name': '知识',
            'title': item.title,
            'description': f"{item.content[:50]}..." if len(item.content) > 50 else item.content,
            'url': f"/knowledge/item/{item.id}",
            'time_ago': time_ago,
            'created_at': item.created_at,
            'icon': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>',
        })

    # 获取最近的文件
    recent_files = FileLibrary.query.order_by(
        FileLibrary.created_at.desc()
    ).limit(3).all()

    for file in recent_files:
        time_ago = get_time_ago(file.created_at)
        recent_activities.append({
            'type': 'file',
            'type_name': '文件',
            'title': file.title,
            'description': file.description[:50] + "..." if file.description and len(file.description) > 50 else (
                        file.description or file.original_name),
            'url': f"/file/{file.id}/view",
            'time_ago': time_ago,
            'created_at': file.created_at,
            'icon': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>',
        })

    # 按时间排序，取最近的10条
    recent_activities.sort(key=lambda x: x['created_at'], reverse=True)
    recent_activities = recent_activities[:10]

    return render_template(
        "main/index.html",
        current_date=current_date,
        weekday=weekday,
        stats=stats,
        recent_activities=recent_activities,
    )


def get_time_ago(dt):
    """计算时间差并返回友好的字符串"""
    now = datetime.now()

    # 确保 dt 是 datetime 对象
    if not isinstance(dt, datetime):
        return "未知时间"

    diff = now - dt

    if diff.days > 30:
        months = diff.days // 30
        return f"{months}个月前"
    elif diff.days > 0:
        return f"{diff.days}天前"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours}小时前"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes}分钟前"
    else:
        return "刚刚"