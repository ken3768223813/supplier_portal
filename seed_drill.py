"""
默译冲刺起步句库 —— 一次性导入
用法（在 portal 根目录、激活虚拟环境后）：
    python seed_drill.py

句子覆盖：会议胶水语 / 审核 / 金相材料 / 表面处理 / 电气 / 测量
都贴 SQE 现场，可按需增删。重复运行不会重复插入（按中文去重）。
"""
from app import create_app          # ← 按你的工厂函数名调整
from app.extensions import db
from app.models import DrillPhrase

PHRASES = [
    # ── 会议胶水语 meeting ──（专业词你都会，真正卡壳的往往是这些连接句）
    ("meeting", "我先介绍一下今天的审核议程。",
     "Let me walk you through today's audit agenda.",
     "audit agenda", "开场用，把现场节奏先攥在自己手里"),
    ("meeting", "能麻烦你带我们走一遍这个工序是怎么管控的吗？",
     "Could you walk us through how this process is controlled?",
     "walk us through, controlled", "审核追问万能句，几乎每次现场都用得上"),
    ("meeting", "确认一下，你的意思是……？",
     "Just to confirm, you're saying that...?",
     "Just to confirm", "陪同翻译时澄清用，避免会错意"),
    ("meeting", "我们能先回到上一个问题吗？",
     "Can we go back to the previous point for a moment?",
     "go back to", None),
    ("meeting", "这点我们稍后再讨论。",
     "Let's come back to this later.",
     "come back to", None),
    ("meeting", "他的意思是……（转述供应商）",
     "What he means is that...",
     "What he means", "口译转述常用开头，先接住再翻"),
    ("meeting", "我们先这样定，细节会后再敲。",
     "Let's align on this for now and sort out the details later.",
     "align, sort out", None),
    ("meeting", "我需要先跟我同事确认一下。",
     "I'll need to check with my colleague first.",
     "check with", "给自己留缓冲，别被现场逼着当场表态"),

    # ── 审核 audit ──
    ("audit", "这批样件数量不满足最小要求。",
     "The sample quantity does not meet the minimum requirement.",
     "sample quantity, minimum requirement", "findings 中性表述，不带情绪、不夸大严重度"),
    ("audit", "纠正措施还没有完全落实到位。",
     "The corrective action has not been fully implemented.",
     "corrective action, implemented", None),
    ("audit", "请提供这一批的检验记录。",
     "Please provide the inspection records for this lot.",
     "inspection records, lot", None),
    ("audit", "这个偏差需要一份正式的让步申请。",
     "This deviation requires a formal concession request.",
     "deviation, concession request", None),
    ("audit", "我们把它定为一个重要不符合项。",
     "We'll classify this as a major nonconformity.",
     "major nonconformity", "critical / major / minor 三档要张口就分得清"),
    ("audit", "这个测试方法和标准要求不一致。",
     "The test method is not consistent with the standard requirement.",
     "consistent with", None),

    # ── 金相材料 metallurgy ──
    ("metallurgy", "我们在弹簧表面发现了完全的铁素体脱碳。",
     "We found complete ferritic decarburization on the spring surface.",
     "ferritic decarburization", None),
    ("metallurgy", "金相检验显示存在折叠缺陷。",
     "The metallographic examination shows folding defects.",
     "metallographic examination, folding", None),
    ("metallurgy", "硬度低于规格下限。",
     "The hardness is below the lower specification limit.",
     "lower specification limit", None),

    # ── 表面处理 surface ──
    ("surface", "这个零件按 2882 标准做表面处理。",
     "This part is surface-treated per standard 2882.",
     "surface-treated, per", "per = 按照……，审核里高频"),
    ("surface", "盐雾测试结果不合格。",
     "The salt spray test result is unacceptable.",
     "salt spray test", None),

    # ── 电气 electrical ──
    ("electrical", "供应商无法提供这一批的耐压测试记录。",
     "The supplier could not show the hipot test records for this batch.",
     "hipot test, batch", "hipot = high-potential，耐压/绝缘测试"),
    ("electrical", "我们需要确认接地连续性。",
     "We need to verify the ground continuity.",
     "ground continuity", None),
    ("electrical", "这个信号在示波器上有明显的噪声。",
     "There is noticeable noise on this signal on the oscilloscope.",
     "noise, oscilloscope", None),

    # ── 测量 measurement ──
    ("measurement", "请用这个量具复测一下这个尺寸。",
     "Please re-measure this dimension with this gauge.",
     "re-measure, gauge", None),
    ("measurement", "这个特性需要做一次 MSA 分析。",
     "This characteristic requires an MSA study.",
     "characteristic, MSA study", "MSA = 测量系统分析"),
]


def run():
    app = create_app()
    with app.app_context():
        existing = {p.cn for p in DrillPhrase.query.all()}
        added = 0
        for cat, cn, en, terms, note in PHRASES:
            if cn in existing:
                continue
            db.session.add(DrillPhrase(
                category=cat, cn=cn, en=en,
                key_terms=terms, note=note, source="seed"
            ))
            added += 1
        db.session.commit()
        print(f"导入完成：新增 {added} 句，库内共 {DrillPhrase.query.count()} 句。")


if __name__ == "__main__":
    run()