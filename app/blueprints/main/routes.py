from flask import render_template
from . import main_bp

@main_bp.get("/")
def index():
    # 先给首页一些假数据，未来换成数据库统计即可
    stats = [
        {"label": "供应商总数", "value": 128, "hint": "已建档供应商"},
        {"label": "待补资料", "value": 23, "hint": "缺少PPAP/证书等"},
        {"label": "本周新增提交", "value": 41, "hint": "上传/更新次数"},
        {"label": "待审核", "value": 9, "hint": "等待SQE确认"},
    ]

    todo = [
        {"title": "完善供应商资料上传模块", "tag": "Next", "desc": "支持多文件、分类、版本号"},
        {"title": "加供应商主数据页面", "tag": "Soon", "desc": "供应商代码、联系人、工厂信息"},
        {"title": "加资料审核流程", "tag": "Soon", "desc": "审核状态、驳回原因、通知"},
    ]

    recent = [
        {"supplier": "ZSU0026419", "type": "证书更新", "time": "今天", "status": "已提交"},
        {"supplier": "ITMD10793", "type": "PPAP资料", "time": "昨天", "status": "待审核"},
        {"supplier": "ITV0014680", "type": "8D报告", "time": "1/12", "status": "已通过"},
    ]

    return render_template("main/index.html", stats=stats, todo=todo, recent=recent)
