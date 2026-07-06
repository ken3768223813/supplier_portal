"""
默译冲刺 Drill 蓝图
- /drill            管理页：查看 / 添加 / 删除句子，按分类筛选
- /drill/add        新增句子 (POST)
- /drill/delete/<id> 删除句子 (POST)
- /drill/export     生成并下载「离线默译 HTML」（自包含、零外部依赖、地铁可用）

注册方式（在 app 工厂 app/__init__.py 里，跟 tr/cp 那些放一起）：
    from .blueprints.drill import drill_bp
    app.register_blueprint(drill_bp)
"""
import json
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, Response, flash
)

# 本文件位于 app/blueprints/drill/__init__.py
# 三个点：drill -> blueprints -> app，才够到 app/extensions.py 和 app/models.py
from ...extensions import db
from ...models import DrillPhrase

drill_bp = Blueprint(
    'drill', __name__,
    url_prefix='/drill'
)
# 注意：不设 template_folder。
# 你的模板是中央集中式（app/templates/<蓝图名>/），所以模板放 app/templates/drill/，
# render_template('drill/xxx.html') 会自动从中央 templates 里找。

# 分类定义：value -> 中文标签（管理页和离线页共用同一套）
CATEGORIES = [
    ('meeting',     '会议胶水语'),
    ('audit',       '审核'),
    ('metallurgy',  '金相材料'),
    ('surface',     '表面处理'),
    ('electrical',  '电气'),
    ('measurement', '测量'),
]
CATEGORY_MAP = dict(CATEGORIES)


@drill_bp.route('/')
def index():
    cat = request.args.get('cat', '').strip()
    q = DrillPhrase.query.filter_by(active=True)
    if cat:
        q = q.filter_by(category=cat)
    phrases = q.order_by(DrillPhrase.category, DrillPhrase.created_at.desc()).all()

    # 各分类计数（给筛选 pill 用）
    counts = {}
    for value, _ in CATEGORIES:
        counts[value] = DrillPhrase.query.filter_by(active=True, category=value).count()
    total = DrillPhrase.query.filter_by(active=True).count()

    return render_template(
        'drill/index.html',
        phrases=phrases,
        categories=CATEGORIES,
        category_map=CATEGORY_MAP,
        current_cat=cat,
        counts=counts,
        total=total,
    )


@drill_bp.route('/add', methods=['POST'])
def add():
    cn = (request.form.get('cn') or '').strip()
    en = (request.form.get('en') or '').strip()
    if not cn or not en:
        flash('中文和英文参考都要填', 'error')
        return redirect(url_for('drill.index'))

    p = DrillPhrase(
        category=(request.form.get('category') or 'meeting').strip(),
        cn=cn,
        en=en,
        key_terms=(request.form.get('key_terms') or '').strip() or None,
        note=(request.form.get('note') or '').strip() or None,
        source=(request.form.get('source') or '').strip() or None,
    )
    db.session.add(p)
    db.session.commit()
    return redirect(url_for('drill.index', cat=p.category))


@drill_bp.route('/delete/<int:pid>', methods=['POST'])
def delete(pid):
    p = DrillPhrase.query.get_or_404(pid)
    cat = p.category
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for('drill.index', cat=cat))


@drill_bp.route('/export')
def export():
    """
    生成离线默译 HTML 并作为附件下载。
    可选 query 参数：
        ?cat=audit       只导出某分类（默认全部）
        ?limit=80        最多导出多少条（默认全部）
    """
    cat = request.args.get('cat', '').strip()
    limit = request.args.get('limit', type=int)

    q = DrillPhrase.query.filter_by(active=True)
    if cat:
        q = q.filter_by(category=cat)
    q = q.order_by(DrillPhrase.category, DrillPhrase.id)
    if limit:
        q = q.limit(limit)
    phrases = q.all()

    data = [p.to_dict() for p in phrases]
    phrases_json = json.dumps(data, ensure_ascii=False)
    cat_json = json.dumps(CATEGORIES, ensure_ascii=False)

    html = render_template(
        'drill/offline.html',
        phrases_json=phrases_json,
        cat_json=cat_json,
        generated=datetime.now().strftime('%Y-%m-%d %H:%M'),
        count=len(data),
    )

    suffix = f'_{cat}' if cat else ''
    filename = f'drill{suffix}_{datetime.now():%Y%m%d}.html'
    return Response(
        html,
        mimetype='text/html',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )