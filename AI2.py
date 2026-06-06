"""
检查所有 EDC TR 的 issue_description 是否抓取正确
运行：python check_descriptions.py

标记规则：
  🔴 空/过短（<20字）
  🟡 只有模板废话（costs/8D report/invoice 等，没有实际缺陷描述）
  🟢 正常（包含具体缺陷关键词）
"""
import re
from app import create_app
from app.models import TroubleReport

# 模板废话关键词（出现这些说明抓到的是页脚/通用模板，不是实际问题）
BOILERPLATE = [
    "all costs", "will be charged", "assembly line",
    "we ask you to send report", "8d urgently",
    "invoice from", "elimination inconvenience",
    "sample lab", "inspection department",
    "supply quality", "quality supplies",
]

# 实际缺陷关键词（出现这些说明有真正的问题描述）
DEFECT_KEYWORDS = [
    "crack", "leak", "porosity", "misalignment", "dent",
    "paint", "fusion", "melting", "scratch", "corrosion",
    "dimension", "tolerance", "weight", "excess", "broken",
    "defect", "rejected", "failed", "non-compliant",
    "machining", "casting", "assembly", "balancing",
    "damaged", "missing", "deformation", "burr",
    "surface", "fracture", "gap", "worn",
    # Italian
    "ammaccatur", "sfalsamento", "cricca", "porosit",
    "verniciatura", "fusione", "difett",
]

app = create_app()

with app.app_context():
    trs = TroubleReport.query.filter(
        TroubleReport.tr_no.like("TR-EDC-%")
    ).order_by(TroubleReport.tr_no).all()

    bad = []
    suspect = []
    good = []

    for tr in trs:
        desc = (tr.issue_description or "").strip()
        desc_lower = desc.lower()

        # 空或过短
        if len(desc) < 20:
            bad.append(tr)
            continue

        # 检查是否只有废话
        has_boilerplate = sum(1 for kw in BOILERPLATE if kw in desc_lower)
        has_defect = sum(1 for kw in DEFECT_KEYWORDS if kw in desc_lower)

        if has_boilerplate > 0 and has_defect == 0:
            suspect.append(tr)
        elif has_defect == 0 and len(desc) < 80:
            suspect.append(tr)
        else:
            good.append(tr)

    # 输出报告
    print(f"\n{'='*60}")
    print(f"EDC TR 问题描述检查报告")
    print(f"{'='*60}")
    print(f"总计: {len(trs)} 条")
    print(f"  🟢 正常: {len(good)}")
    print(f"  🟡 可疑: {len(suspect)}")
    print(f"  🔴 异常: {len(bad)}")
    print()

    if bad:
        print(f"{'─'*60}")
        print(f"🔴 异常（空/过短，需要修复）：")
        print(f"{'─'*60}")
        for tr in bad:
            desc = (tr.issue_description or "")[:60]
            print(f"  {tr.tr_no}  |  {repr(desc)}")
        print()

    if suspect:
        print(f"{'─'*60}")
        print(f"🟡 可疑（可能抓到了模板废话，需人工确认）：")
        print(f"{'─'*60}")
        for tr in suspect:
            desc = (tr.issue_description or "").strip()
            preview = desc[:80].replace("\n", " ")
            summary = (tr.issue_summary or "—")[:50]
            print(f"  {tr.tr_no}")
            print(f"    原文: {preview}...")
            print(f"    AI:   {summary}")
            print()

    if good:
        print(f"{'─'*60}")
        print(f"🟢 正常（{len(good)} 条，仅列出前 5 条）：")
        print(f"{'─'*60}")
        for tr in good[:5]:
            desc = (tr.issue_description or "").strip()[:60].replace("\n", " ")
            summary = (tr.issue_summary or "—")[:50]
            print(f"  {tr.tr_no}  |  AI: {summary}")

    print(f"\n{'='*60}")
    if bad or suspect:
        print(f"⚠ 共 {len(bad)+len(suspect)} 条需要检查/修复")
        print(f"  修复方法：对照 EDC PDF 原文，用 fix_3tr.py 模式手动更正")
    else:
        print(f"✅ 全部正常！")