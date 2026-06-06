"""
本地 AI 助手 —— Ollama (Qwen/Llama) 提取 EDC 问题摘要 + 8D 根因/措施
放到 app/ai_helper.py
"""
import re
import json
import requests
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:8b"   # 英文输出可改 llama3.2:3b

# 输出语言：'zh' 中文 / 'en' 英文
OUTPUT_LANG = "en"


# ──────────────────────────────────────────────────────────
# Ollama 基础
# ──────────────────────────────────────────────────────────

def is_ollama_available(timeout=3):
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _call_ollama(prompt, timeout=120, num_predict=300, logger=None):
    """调用 Ollama，返回文本或 None"""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.2, "num_predict": num_predict},
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            if logger:
                logger.warning(f"[AI] Ollama returned {resp.status_code}")
            return None
        raw = (resp.json().get("response") or "").strip()
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        return raw if raw else None
    except requests.exceptions.Timeout:
        if logger:
            logger.warning("[AI] Ollama timeout")
        return None
    except requests.exceptions.ConnectionError:
        if logger:
            logger.warning("[AI] Ollama not running")
        return None
    except Exception as e:
        if logger:
            logger.warning(f"[AI] error: {e}")
        return None


def _parse_json(text):
    """从模型输出中稳健提取 JSON"""
    if not text:
        return None
    text = text.strip()
    # 去掉 ```json ``` 围栏
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # 抓第一个 { 到最后一个 }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    try:
        return json.loads(text)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────
# 1) EDC 问题描述摘要
# ──────────────────────────────────────────────────────────

_SUMMARY_PROMPT = {
    "en": """You are an automotive parts quality engineer. Below is the raw issue description from an EDC quality report. It may contain Italian/English text, formatting symbols, and irrelevant info.

CRITICAL RULES:
- Extract ONLY the specific defect/failure description from the text.
- Do NOT mention: 8D report requests, cost charges, supplier actions, rejection/selection processes, or administrative instructions. These are irrelevant.
- Do NOT state obvious facts like "parts were rejected" or "non-conforming parts found" — every EDC report has rejections, that is not useful information.
- Do NOT include quantities or piece counts.
- Focus ONLY on: what is the SPECIFIC technical defect? (e.g., cracks, porosity, paint defects, leakage, excess weight, dimensional deviation, surface dents)
- If the report does NOT describe any specific defect characteristics, output exactly: "No specific defect described in report, further investigation needed."
- NEVER invent or guess a defect type not explicitly stated in the text.

Summarize the specific defect in ONE concise English sentence (max 15 words).
Output only the summary, no prefix/quotes/explanation.

Raw text:
{raw}""",
}


def summarize_issue(raw_text, timeout=180, logger=None):
    if not raw_text or not raw_text.strip():
        return None
    if len(raw_text.strip()) < 30:
        return raw_text.strip()

    prompt = _SUMMARY_PROMPT[OUTPUT_LANG].format(raw=raw_text.strip()[:2000])
    summary = _call_ollama(prompt, timeout=timeout, num_predict=800, logger=logger)
    if not summary:
        return None

    for prefix in ["概括：", "概括:", "问题：", "总结：", "Summary:", "Issue:"]:
        if summary.startswith(prefix):
            summary = summary[len(prefix):].strip()
    summary = summary.strip("\"'「」“”").strip()
    return summary or None


# ──────────────────────────────────────────────────────────
# 2) 8D 报告文本提取（Excel / PDF / Word / Email）
# ──────────────────────────────────────────────────────────

def extract_text_from_file(file_path, logger=None):
    """从 8D 报告文件提取纯文本。支持 xlsx/xls/pdf/docx/txt。"""
    p = Path(file_path)
    if not p.exists():
        return ""
    ext = p.suffix.lower().lstrip(".")

    try:
        # ── Excel（你的 8D 主要格式）──
        if ext == "xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(str(p), data_only=True, read_only=True)
            lines = []
            for ws in wb.worksheets:
                lines.append(f"=== Sheet: {ws.title} ===")
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                    if cells:
                        lines.append(" | ".join(cells))
            wb.close()
            return "\n".join(lines)

        # ── 老 Excel 格式 ──
        elif ext == "xls":
            try:
                import xlrd
                wb = xlrd.open_workbook(str(p))
                lines = []
                for sheet in wb.sheets():
                    for r in range(sheet.nrows):
                        cells = [str(sheet.cell_value(r, c)).strip() for c in range(sheet.ncols)]
                        cells = [c for c in cells if c]
                        if cells:
                            lines.append(" | ".join(cells))
                return "\n".join(lines)
            except ImportError:
                if logger:
                    logger.warning("[AI] xls needs: pip install xlrd")
                return ""

        # ── PDF ──
        elif ext == "pdf":
            import pdfplumber
            with pdfplumber.open(str(p)) as pdf:
                return "\n".join(pg.extract_text() or "" for pg in pdf.pages)

        # ── Word ──
        elif ext == "docx":
            import docx
            d = docx.Document(str(p))
            parts = [para.text for para in d.paragraphs if para.text.strip()]
            # 也读表格
            for table in d.tables:
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        parts.append(" | ".join(cells))
            return "\n".join(parts)

        # ── 纯文本 ──
        elif ext == "txt":
            return p.read_text(encoding="utf-8", errors="ignore")

        else:
            if logger:
                logger.info(f"[AI] unsupported 8D format: {ext}")
            return ""

    except Exception as e:
        if logger:
            logger.warning(f"[AI] text extract failed for {p.name}: {e}")
        return ""


# ──────────────────────────────────────────────────────────
# 3) 8D 根因 + 纠正措施提取
# ──────────────────────────────────────────────────────────

_8D_PROMPT = {
    "zh": """你是汽车质量工程师，正在分析一份 8D 报告。下面是从 8D 报告提取的文本内容（可能含中英意文、用 | 分隔的表格数据）。

请提取两项关键信息：
1. root_cause（根本原因 / D4）：问题产生的根本原因
2. corrective_action（纠正措施 / D5/D6）：采取的永久纠正和预防措施

严格按以下 JSON 格式输出（值用中文），不要任何其他文字：
{{"root_cause": "...", "corrective_action": "..."}}

找不到的字段填空字符串。措施如有多条，用分号或换行分隔，保持简洁。

8D 报告文本：
{raw}""",
    "en": """You are a quality engineer analyzing an 8D report. Below is text extracted from an 8D report (may contain Chinese/English/Italian, table data with | separators).

Extract two key items:
1. root_cause (D4): the fundamental cause of the problem
2. corrective_action (D5/D6): permanent corrective and preventive actions taken

Output STRICTLY in this JSON format (values in English), nothing else:
{{"root_cause": "...", "corrective_action": "..."}}

Use empty string if a field is not found. Keep concise; separate multiple actions with semicolons.

8D report text:
{raw}""",
}


def extract_8d(file_path, timeout=150, logger=None):
    """从 8D 报告文件提取根因和纠正措施。返回 (root_cause, action) 或 (None, None)。"""
    raw = extract_text_from_file(file_path, logger=logger)
    if not raw or len(raw.strip()) < 20:
        if logger:
            logger.info(f"[AI] 8D text too short: {file_path}")
        return None, None

    prompt = _8D_PROMPT[OUTPUT_LANG].format(raw=raw.strip()[:4000])
    out = _call_ollama(prompt, timeout=timeout, num_predict=500, logger=logger)
    if not out:
        return None, None

    data = _parse_json(out)
    if not data:
        if logger:
            logger.warning(f"[AI] 8D JSON parse failed: {out[:100]}")
        return None, None

    rc = (data.get("root_cause") or "").strip()
    ac = (data.get("corrective_action") or "").strip()
    if logger:
        logger.info(f"[AI] 8D extracted: cause={rc[:30]}... action={ac[:30]}...")
    return (rc or None), (ac or None)