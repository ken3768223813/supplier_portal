# 存成 fix_vague.py
from app import create_app
from app.extensions import db
from app.models import TroubleReport
from app.ai_helper import summarize_issue

app = create_app()
with app.app_context():
    tr = TroubleReport.query.filter_by(tr_no="TR-EDC-201638053").first()
    tr.issue_summary = None
    db.session.commit()
    s = summarize_issue(tr.issue_description)
    print(f"NEW: {s}")
    if s:
        tr.issue_summary = s
        db.session.commit()