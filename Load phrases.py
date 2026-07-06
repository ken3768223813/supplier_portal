"""
SQE 英语口语句库 · 完整版
覆盖 Ken 作为 SQE 的全部核心场景，按工作中真实会说/会听到的情景组织。
每句都是"你张口就该能说出来"的，不是书面语。

用法（项目根目录）：
    python load_phrases.py

重复运行不会重复插入（按中文去重）。
"""
from app import create_app
from app.extensions import db
from app.models import DrillPhrase

PHRASES = [

    # ════════════════════════════════════════════════════════════════
    # 会议胶水语 · meeting
    # 这些不是专业词，但恰恰是你最卡壳的——连接句、过渡句、争取时间的句子
    # ════════════════════════════════════════════════════════════════

    # ── 开场 / 自我介绍 ──
    ("meeting", "我先介绍一下今天的审核议程。",
     "Let me walk you through today's audit agenda.",
     "walk you through, audit agenda", "开场用，把现场节奏先攥在自己手里"),
    ("meeting", "我是 Piaggio 中国的供应商质量工程师。",
     "I'm a Supplier Quality Engineer from Piaggio China.",
     "Supplier Quality Engineer", None),
    ("meeting", "今天我们主要看三个方面：来料检验、过程控制和出货检验。",
     "Today we'll mainly focus on three areas: incoming inspection, process control, and outgoing inspection.",
     "incoming inspection, process control, outgoing inspection", "审核开场三段式，先定框架"),

    # ── 追问 / 深挖 ──
    ("meeting", "能麻烦你带我们走一遍这个工序是怎么管控的吗？",
     "Could you walk us through how this process is controlled?",
     "walk us through, controlled", "审核追问万能句"),
    ("meeting", "这个你能再展开说一下吗？",
     "Could you elaborate on that?",
     "elaborate", None),
    ("meeting", "具体是怎么操作的？能让我看一下实际的记录吗？",
     "How exactly is this done in practice? Can I see the actual records?",
     "in practice, actual records", "审核不能只听嘴说，要看记录"),
    ("meeting", "这个规定是写在哪个文件里的？",
     "Which document specifies this requirement?",
     "specifies this requirement", None),
    ("meeting", "上次审核提的问题，现在进展怎么样了？",
     "What's the status of the findings from the last audit?",
     "status, findings", None),

    # ── 澄清 / 确认 ──
    ("meeting", "确认一下，你的意思是……？",
     "Just to confirm, you're saying that...?",
     "Just to confirm", "陪同翻译时澄清用"),
    ("meeting", "等一下，我没太跟上。你能再说一遍吗？",
     "Hold on, I didn't quite follow. Could you say that again?",
     "didn't quite follow", "别怕说这句，比装懂强一百倍"),
    ("meeting", "我理解你的意思是……，对吗？",
     "So what you're saying is..., is that correct?",
     "is that correct", None),
    ("meeting", "这个数据和你刚才说的对不上，能解释一下吗？",
     "This data doesn't match what you just mentioned. Could you clarify?",
     "doesn't match, clarify", None),

    # ── 过渡 / 控场 ──
    ("meeting", "好，这个点我们先记下来。接下来看下一个工序。",
     "OK, let's note this point and move on to the next process.",
     "note this point, move on", None),
    ("meeting", "我们能先回到上一个问题吗？",
     "Can we go back to the previous point for a moment?",
     "go back to", None),
    ("meeting", "这点我们稍后再讨论。",
     "Let's come back to this later.",
     "come back to", None),
    ("meeting", "时间关系，我们跳过这部分，直接看关键工序。",
     "Due to time constraints, let's skip this section and go directly to the key processes.",
     "time constraints, key processes", None),

    # ── 转述 / 口译 ──
    ("meeting", "他的意思是……（转述供应商）",
     "What he means is that...",
     "What he means", "口译转述常用开头"),
    ("meeting", "供应商说他们已经在整改了，预计下周完成。",
     "The supplier says they are already working on the correction and expect to finish by next week.",
     "working on the correction", None),
    ("meeting", "让我把这个翻译给供应商听。",
     "Let me translate this for the supplier.",
     None, None),
    ("meeting", "你的问题我需要用中文跟他们确认一下。",
     "Let me confirm your question with them in Chinese.",
     None, "给自己争取翻译缓冲时间"),

    # ── 收尾 / 共识 ──
    ("meeting", "我们先这样定，细节会后再敲。",
     "Let's align on this for now and sort out the details later.",
     "align, sort out", None),
    ("meeting", "我需要先跟我同事确认一下。",
     "I'll need to check with my colleague first.",
     "check with", "给自己留缓冲"),
    ("meeting", "我来总结一下今天的行动项。",
     "Let me summarize today's action items.",
     "action items", None),
    ("meeting", "每个行动项请确认负责人和完成时间。",
     "Please confirm the responsible person and deadline for each action item.",
     "responsible person, deadline", None),
    ("meeting", "今天先到这里，审核报告我们会在两周内发给你们。",
     "Let's wrap up here. We'll send the audit report within two weeks.",
     "wrap up, within two weeks", None),

    # ── 表达异议 / 施压（中性、不带情绪）──
    ("meeting", "这个解释我们没法接受。",
     "I'm afraid we cannot accept this explanation.",
     "I'm afraid, cannot accept", "中性但坚定，不卑不亢"),
    ("meeting", "这个问题已经反复出现过了，我们需要看到系统性的改善。",
     "This issue has been recurring. We need to see systematic improvement.",
     "recurring, systematic improvement", None),
    ("meeting", "如果下次审核还是同样的问题，我们会考虑升级处理。",
     "If we see the same issue at the next audit, we'll consider escalating.",
     "escalating", None),

    # ════════════════════════════════════════════════════════════════
    # 审核 · audit
    # ════════════════════════════════════════════════════════════════

    # ── 提问 / 要求提供证据 ──
    ("audit", "请提供这一批的检验记录。",
     "Please provide the inspection records for this lot.",
     "inspection records, lot", None),
    ("audit", "你们的控制计划里这个参数的抽样频次是多少？",
     "What's the sampling frequency for this parameter in your control plan?",
     "sampling frequency, control plan", None),
    ("audit", "这台设备的校准证书在有效期内吗？",
     "Is the calibration certificate for this equipment still valid?",
     "calibration certificate, valid", None),
    ("audit", "你们做过过程 FMEA 吗？能让我看一下吗？",
     "Have you conducted a process FMEA? Can I take a look?",
     "process FMEA", None),
    ("audit", "这个工序有没有作业指导书？操作员知道怎么做吗？",
     "Is there a work instruction for this process? Does the operator know how to follow it?",
     "work instruction, operator", None),
    ("audit", "你们的来料检验具体检什么项目？",
     "What specific items do you check during incoming inspection?",
     "incoming inspection", None),
    ("audit", "不合格品是怎么隔离和标识的？",
     "How are nonconforming parts segregated and identified?",
     "segregated, identified", None),
    ("audit", "追溯性怎么保证？能从成品追回到原材料批次吗？",
     "How is traceability ensured? Can you trace from finished goods back to the raw material lot?",
     "traceability, trace back", None),
    ("audit", "你们用的是哪个版本的图纸？和我们最新版一致吗？",
     "Which revision of the drawing are you using? Is it consistent with our latest version?",
     "revision, consistent with", None),
    ("audit", "变更管理流程是怎样的？有没有经过客户批准？",
     "What's your change management process? Has the change been approved by the customer?",
     "change management, approved by the customer", None),

    # ── Findings 讨论 ──
    ("audit", "这批样件数量不满足最小要求。",
     "The sample quantity does not meet the minimum requirement.",
     "sample quantity, minimum requirement", "中性表述，不夸大严重度"),
    ("audit", "纠正措施还没有完全落实到位。",
     "The corrective action has not been fully implemented.",
     "corrective action, implemented", None),
    ("audit", "这个偏差需要一份正式的让步申请。",
     "This deviation requires a formal concession request.",
     "deviation, concession request", None),
    ("audit", "我们把它定为一个重要不符合项。",
     "We'll classify this as a major nonconformity.",
     "major nonconformity", "critical / major / minor 三档要分清"),
    ("audit", "这个测试方法和标准要求不一致。",
     "The test method is not consistent with the standard requirement.",
     "consistent with", None),
    ("audit", "控制计划和作业指导书之间有矛盾，参数不一样。",
     "There's a discrepancy between the control plan and the work instruction. The parameters don't match.",
     "discrepancy, don't match", None),
    ("audit", "记录上显示有超差，但没有看到处理记录。",
     "The records show out-of-spec results, but I don't see any disposition records.",
     "out-of-spec, disposition", None),
    ("audit", "这个问题我先记为观察项，不算不符合。",
     "I'll record this as an observation, not a nonconformity.",
     "observation", None),
    ("audit", "你们的反应计划写的是什么？实际执行了吗？",
     "What does your reaction plan say? Was it actually followed?",
     "reaction plan", None),

    # ── 过程审核专用 (VDA 6.3 / ANFIA) ──
    ("audit", "这个工序的过程能力 Cpk 是多少？",
     "What's the process capability Cpk for this operation?",
     "process capability, Cpk", None),
    ("audit", "SPC 控制图有没有异常趋势？",
     "Are there any abnormal trends on the SPC control chart?",
     "SPC control chart, abnormal trends", None),
    ("audit", "防错装置上次验证是什么时候？",
     "When was the poka-yoke device last verified?",
     "poka-yoke, verified", None),
    ("audit", "换型/换模时的首件检验流程是什么？",
     "What's the first-piece inspection procedure after a changeover?",
     "first-piece inspection, changeover", None),
    ("audit", "老化/烧机测试的参数够不够筛出早期失效？",
     "Are the burn-in test parameters sufficient to screen out infant mortality failures?",
     "burn-in, infant mortality", "你在 ADAYO 审核时碰过这个问题"),

    # ════════════════════════════════════════════════════════════════
    # 8D / 问题解决 · problem_solving（归入 audit 分类）
    # ════════════════════════════════════════════════════════════════

    ("audit", "请在五个工作日内提交 8D 报告。",
     "Please submit the 8D report within five working days.",
     "8D report, working days", None),
    ("audit", "D3 遏制措施做了没有？在制品和库存都排查了吗？",
     "Has D3 containment been implemented? Have you screened both WIP and inventory?",
     "containment, WIP, screened", None),
    ("audit", "根本原因分析不够深，请用五个为什么再往下挖。",
     "The root cause analysis isn't deep enough. Please drill down further using 5-Why.",
     "root cause analysis, 5-Why, drill down", None),
    ("audit", "纠正措施和预防措施不能写一样的。",
     "The corrective action and preventive action should not be the same.",
     "corrective action, preventive action", None),
    ("audit", "这个 8D 太表面了，打回去重写。",
     "This 8D is too superficial. Please revise and resubmit.",
     "superficial, revise", None),
    ("audit", "遏制措施要覆盖所有可能受影响的批次。",
     "The containment action must cover all potentially affected lots.",
     "containment, affected lots", None),
    ("audit", "流出原因是什么？为什么没有在出货检验时拦住？",
     "What's the escape cause? Why wasn't it caught during outgoing inspection?",
     "escape cause, outgoing inspection", None),

    # ════════════════════════════════════════════════════════════════
    # 金相材料 · metallurgy
    # ════════════════════════════════════════════════════════════════

    ("metallurgy", "我们在弹簧表面发现了完全的铁素体脱碳。",
     "We found complete ferritic decarburization on the spring surface.",
     "ferritic decarburization", None),
    ("metallurgy", "金相检验显示存在折叠缺陷。",
     "The metallographic examination shows folding defects.",
     "metallographic examination, folding", None),
    ("metallurgy", "硬度低于规格下限。",
     "The hardness is below the lower specification limit.",
     "lower specification limit", None),
    ("metallurgy", "硬度要求是 HRC 58 到 62，实测只有 55。",
     "The hardness requirement is HRC 58 to 62, but the actual reading is only 55.",
     "HRC, actual reading", None),
    ("metallurgy", "这个材质证明上的化学成分和标准对不上。",
     "The chemical composition on the mill certificate doesn't match the standard.",
     "mill certificate, chemical composition", None),
    ("metallurgy", "晶粒度等级是多少？符合要求吗？",
     "What's the grain size rating? Does it meet the requirement?",
     "grain size", None),
    ("metallurgy", "热处理炉温均匀性有没有做过验证？",
     "Has the furnace temperature uniformity been validated?",
     "furnace temperature uniformity", None),
    ("metallurgy", "淬火介质的温度和浓度有没有监控记录？",
     "Are there monitoring records for the quenching medium temperature and concentration?",
     "quenching medium", None),
    ("metallurgy", "抛丸强度用 Almen 试片验证了吗？",
     "Was the shot peening intensity verified with Almen strips?",
     "shot peening, Almen strips", "你在弹簧审核时关注过这个"),
    ("metallurgy", "脱碳层深度超标了，需要评估对疲劳寿命的影响。",
     "The decarburization depth exceeds the limit. We need to assess the impact on fatigue life.",
     "decarburization depth, fatigue life", None),

    # ════════════════════════════════════════════════════════════════
    # 表面处理 · surface
    # ════════════════════════════════════════════════════════════════

    ("surface", "这个零件按 2882 标准做表面处理。",
     "This part is surface-treated per standard 2882.",
     "surface-treated, per", "per = 按照，审核里高频"),
    ("surface", "盐雾测试结果不合格。",
     "The salt spray test result is unacceptable.",
     "salt spray test", None),
    ("surface", "涂层厚度没有达到最小要求。",
     "The coating thickness does not meet the minimum requirement.",
     "coating thickness", None),
    ("surface", "附着力测试用的是百格法还是拉拔法？",
     "Was the adhesion test done by cross-cut or pull-off method?",
     "adhesion test, cross-cut, pull-off", None),
    ("surface", "电泳槽液的 pH 值和温度有没有日常监控？",
     "Is there daily monitoring of the pH and temperature of the CED bath?",
     "CED bath, pH, daily monitoring", None),
    ("surface", "前处理的磷化膜重是多少？",
     "What's the phosphate coating weight in the pretreatment process?",
     "phosphate coating weight, pretreatment", None),
    ("surface", "烘烤温度和时间符合工艺窗口吗？",
     "Are the baking temperature and time within the process window?",
     "baking, process window", None),
    ("surface", "镀层有起泡和剥落现象。",
     "The plating shows blistering and peeling.",
     "blistering, peeling", None),

    # ════════════════════════════════════════════════════════════════
    # 电气 · electrical
    # ════════════════════════════════════════════════════════════════

    ("electrical", "供应商无法提供这一批的耐压测试记录。",
     "The supplier could not show the hipot test records for this batch.",
     "hipot test", "hipot = high-potential，耐压/绝缘测试"),
    ("electrical", "我们需要确认接地连续性。",
     "We need to verify the ground continuity.",
     "ground continuity", None),
    ("electrical", "这个信号在示波器上有明显的噪声。",
     "There is noticeable noise on this signal on the oscilloscope.",
     "noise, oscilloscope", None),
    ("electrical", "绝缘电阻的测试电压和标准要求不一致。",
     "The test voltage for insulation resistance doesn't match the standard requirement.",
     "insulation resistance, test voltage", None),
    ("electrical", "ESD 防护措施到位吗？接地手环有没有每天测试？",
     "Are the ESD protection measures in place? Is the wrist strap tested daily?",
     "ESD, wrist strap", None),
    ("electrical", "PCB 外观检验有没有 AOI？",
     "Do you use AOI for PCB visual inspection?",
     "AOI, PCB", "AOI = 自动光学检测"),
    ("electrical", "回流焊的温度曲线多久验证一次？",
     "How often is the reflow soldering temperature profile validated?",
     "reflow soldering, temperature profile", None),
    ("electrical", "ICT 测试的覆盖率是多少？",
     "What's the coverage rate of your ICT testing?",
     "ICT, coverage rate", "ICT = 在线测试"),
    ("electrical", "功能测试 100% 全检还是抽检？",
     "Is functional testing done on 100% of units or by sampling?",
     "functional testing, sampling", None),
    ("electrical", "软件版本和我们批准的不一致，这是一个严重问题。",
     "The software version doesn't match what we approved. This is a critical issue.",
     "software version, approved", "你在 ADAYO 审核碰过 SW 版本偏差"),

    # ════════════════════════════════════════════════════════════════
    # 测量 · measurement
    # ════════════════════════════════════════════════════════════════

    ("measurement", "请用这个量具复测一下这个尺寸。",
     "Please re-measure this dimension with this gauge.",
     "re-measure, gauge", None),
    ("measurement", "这个特性需要做一次 MSA 分析。",
     "This characteristic requires an MSA study.",
     "MSA study", "MSA = 测量系统分析"),
    ("measurement", "GR&R 结果超过 30% 了，这个量具不能用。",
     "The GR&R result exceeds 30%. This gauge is not acceptable.",
     "GR&R, exceeds", None),
    ("measurement", "校准过期了，用这个量具测的数据都不可信。",
     "The calibration has expired. Any data measured with this gauge is unreliable.",
     "calibration expired, unreliable", None),
    ("measurement", "你们的检具是按哪个图纸版本做的？",
     "Which drawing revision was this checking fixture built to?",
     "checking fixture, drawing revision", None),
    ("measurement", "三坐标测量的基准和图纸定义一致吗？",
     "Are the CMM datum references consistent with the drawing definition?",
     "CMM, datum references", None),
    ("measurement", "测量不确定度有没有评估过？",
     "Has the measurement uncertainty been evaluated?",
     "measurement uncertainty", None),
    ("measurement", "这个公差太紧了，你们的设备精度够吗？",
     "This tolerance is very tight. Does your equipment have sufficient accuracy?",
     "tolerance, accuracy", None),

    # ════════════════════════════════════════════════════════════════
    # PPAP / 文档 · 归入 audit 分类
    # ════════════════════════════════════════════════════════════════

    ("audit", "PPAP 资料还缺哪几项？",
     "Which PPAP elements are still missing?",
     "PPAP elements", None),
    ("audit", "尺寸报告里有几个尺寸超差了。",
     "Several dimensions in the dimensional report are out of specification.",
     "dimensional report, out of specification", None),
    ("audit", "材质证明需要提供原件，复印件不行。",
     "We need the original material certificate, not a copy.",
     "original material certificate", None),
    ("audit", "产能分析做过吗？能满足我们的量产需求吗？",
     "Has a capacity analysis been done? Can it meet our mass production requirements?",
     "capacity analysis, mass production", None),
    ("audit", "请把全尺寸检验报告发给我确认。",
     "Please send me the full dimensional inspection report for review.",
     "full dimensional inspection report", None),

    # ════════════════════════════════════════════════════════════════
    # 供应商现场对话 · 归入 meeting 分类
    # 这些是你在供应商工厂里走动时会用到的
    # ════════════════════════════════════════════════════════════════

    ("meeting", "能带我去生产线看一下吗？",
     "Could you take me to the production line?",
     "production line", None),
    ("meeting", "这个工位的操作员培训记录在哪里？",
     "Where are the operator training records for this workstation?",
     "operator training records, workstation", None),
    ("meeting", "这些红色标签的是不合格品吗？",
     "Are these red-tagged parts nonconforming?",
     "red-tagged, nonconforming", None),
    ("meeting", "仓库里这些物料先进先出有保证吗？",
     "Is FIFO guaranteed for these materials in the warehouse?",
     "FIFO", None),
    ("meeting", "模具保养记录能给我看一下吗？",
     "Can I see the mold maintenance records?",
     "mold maintenance records", None),
    ("meeting", "这批货什么时候能发？我们这边很急。",
     "When can this shipment be dispatched? It's quite urgent on our end.",
     "dispatched, urgent", None),
    ("meeting", "来料和成品的存放区域有没有明确隔离？",
     "Are the incoming material and finished goods storage areas clearly separated?",
     "clearly separated", None),

    # ════════════════════════════════════════════════════════════════
    # 让步 / 偏差处理 · 归入 audit 分类
    # ════════════════════════════════════════════════════════════════

    ("audit", "这个偏差需要走让步流程，你们先提申请。",
     "This deviation requires a concession process. Please submit the application first.",
     "concession process, application", None),
    ("audit", "让步数量是多少？影响哪些批次？",
     "What's the concession quantity? Which lots are affected?",
     "concession quantity, affected", None),
    ("audit", "这批让步放行的条件是什么？",
     "What are the conditions for releasing this concession lot?",
     "conditions, releasing", None),
    ("audit", "让步不等于长期接受，下一批必须恢复正常。",
     "A concession doesn't mean long-term acceptance. The next lot must meet the normal specification.",
     "long-term acceptance, normal specification", None),

    # ════════════════════════════════════════════════════════════════
    # Debit / 索赔 · 归入 meeting 分类
    # ════════════════════════════════════════════════════════════════

    ("meeting", "这批不合格品我们会发起索赔。",
     "We will initiate a debit note for this nonconforming lot.",
     "debit note, nonconforming lot", None),
    ("meeting", "索赔金额包括分选费用和产线停线损失。",
     "The debit amount includes sorting costs and production line downtime losses.",
     "sorting costs, downtime losses", None),
    ("meeting", "请在收到索赔通知后十个工作日内回复。",
     "Please respond within ten working days of receiving the debit notification.",
     "debit notification, working days", None),
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
                key_terms=terms, note=note, source="v1_full"
            ))
            added += 1
        db.session.commit()
        total = DrillPhrase.query.filter_by(active=True).count()
        print(f"导入完成：新增 {added} 句，库内共 {total} 句。")


if __name__ == "__main__":
    run()