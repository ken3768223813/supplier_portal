"""
清空所有 AI 摘要并用新 prompt 重新生成
运行：python resummary_all.py
"""
import sys, time
from app import create_app
from app.extensions import db
from app.models import TroubleReport
from app.ai_helper import summarize_issue, is_ollama_available

app = create_app()

with app.app_context():
    if not is_ollama_available():
        print("❌ Ollama 未运行")
        sys.exit(1)
    print("✅ Ollama 正常\n")

    # 清空所有摘要
    trs = TroubleReport.query.filter(
        TroubleReport.issue_description.isnot(None),
        TroubleReport.issue_description != ""
    ).all()

    print(f"共 {len(trs)} 条 TR 需要重新生成摘要")
    if input("确认清空并重新生成？(y/N): ").strip().lower() != "y":
        sys.exit(0)

    for tr in trs:
        tr.issue_summary = None
    db.session.commit()
    print(f"已清空 {len(trs)} 条摘要\n")

    start = time.time()
    ok = fail = 0
    for i, tr in enumerate(trs, 1):
        print(f"[{i}/{len(trs)}] {tr.tr_no} ... ", end="", flush=True)
        t0 = time.time()
        s = summarize_issue(tr.issue_description)
        el = time.time() - t0
        if s:
            tr.issue_summary = s
            db.session.commit()
            ok += 1
            print(f"✅ ({el:.1f}s) {s[:50]}")
        else:
            fail += 1
            print(f"❌ ({el:.1f}s)")

    total = time.time() - start
    print(f"\n{'='*50}")
    print(f"完成！成功 {ok}，失败 {fail}，总耗时 {total:.0f}秒")