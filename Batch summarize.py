"""
批量为所有已存在的 EDC TR 生成 AI 问题摘要
运行：python batch_summarize.py

前提：
1. Ollama 已安装并运行（ollama pull qwen2.5:3b）
2. 已运行 add_issue_summary.py 添加字段
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import TroubleReport
from app.ai_helper import summarize_issue, is_ollama_available

app = create_app()

with app.app_context():
    # 检查 Ollama
    if not is_ollama_available():
        print("❌ Ollama 未运行！请先确保：")
        print("   1. Ollama 已安装")
        print("   2. 已拉取模型: ollama pull qwen2.5:3b")
        print("   3. Ollama 服务在后台运行")
        sys.exit(1)

    print("✅ Ollama 服务正常\n")

    # 找所有 EDC TR（只处理还没有摘要的）
    trs = TroubleReport.query.filter(
        TroubleReport.tr_no.like("TR-EDC-%")
    ).all()

    pending = [t for t in trs if t.issue_description and not t.issue_summary]

    print(f"共 {len(trs)} 个 EDC TR，其中 {len(pending)} 个需要生成摘要\n")

    if not pending:
        print("全部已有摘要，无需处理。")
        sys.exit(0)

    confirm = input(f"开始为 {len(pending)} 个 TR 生成 AI 摘要？(y/N): ").strip().lower()
    if confirm != "y":
        print("已取消。")
        sys.exit(0)

    print()
    start = time.time()
    ok = 0
    fail = 0

    for i, tr in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] {tr.tr_no} ... ", end="", flush=True)
        t0 = time.time()
        summary = summarize_issue(tr.issue_description)
        elapsed = time.time() - t0

        if summary:
            tr.issue_summary = summary
            db.session.commit()
            ok += 1
            print(f"✅ ({elapsed:.1f}s) {summary[:40]}")
        else:
            fail += 1
            print(f"❌ ({elapsed:.1f}s) 生成失败")

    total = time.time() - start
    print(f"\n{'='*50}")
    print(f"完成！成功 {ok}，失败 {fail}，总耗时 {total:.0f}秒")
    print(f"平均每条 {total/len(pending):.1f}秒")