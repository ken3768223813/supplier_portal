"""SQE English Lab scheduling and AI material generation."""
from __future__ import annotations

from datetime import date, timedelta
import json
import re

from app.ai_helper import OLLAMA_MODEL, _call_ollama, _parse_json


VALID_RATINGS = {"again", "good", "easy"}
VALID_DIFFICULTIES = {"foundation", "intermediate", "advanced"}


def schedule_review(progress, rating, today=None):
    """Apply a compact three-grade spaced-repetition schedule."""
    if rating not in VALID_RATINGS:
        raise ValueError("Unsupported drill rating")
    today = today or date.today()
    ease = float(getattr(progress, "ease_factor", None) or 2.5)
    interval = int(getattr(progress, "interval_days", None) or 0)
    repetitions = int(getattr(progress, "repetitions", None) or 0)

    if rating == "again":
        repetitions = 0
        interval = 1
        ease = max(1.3, ease - 0.2)
    elif rating == "good":
        repetitions += 1
        if repetitions == 1:
            interval = 2
        elif repetitions == 2:
            interval = 5
        else:
            interval = max(7, round(interval * ease))
    else:
        repetitions += 1
        ease = min(3.2, ease + 0.15)
        if repetitions == 1:
            interval = 4
        elif repetitions == 2:
            interval = 10
        else:
            interval = max(14, round(interval * ease * 1.2))

    return {
        "ease_factor": ease,
        "interval_days": interval,
        "repetitions": repetitions,
        "due_date": today + timedelta(days=interval),
    }


def default_chunks(sentence):
    """Split spoken English into a few meaningful-sized practice blocks."""
    sentence = re.sub(r"\s+", " ", (sentence or "").strip())
    if not sentence:
        return []
    clauses = [
        item.strip()
        for item in re.split(r"(?<=[,;:])\s+|\s+(?=(?:and|but|because|so|which|that)\s)", sentence)
        if item.strip()
    ]
    if 2 <= len(clauses) <= 7:
        return clauses
    words = sentence.split()
    target = 4 if len(words) <= 16 else 5
    return [" ".join(words[index:index + target]) for index in range(0, len(words), target)]


def _clean_card(item, fallback_category):
    if not isinstance(item, dict):
        return None
    cn = str(item.get("cn") or "").strip()
    en = re.sub(r"\s+", " ", str(item.get("en") or "").strip())
    if not cn or not en:
        return None

    terms = item.get("key_terms") or []
    if isinstance(terms, str):
        terms = [part.strip() for part in re.split(r"[,，;；]", terms) if part.strip()]
    elif isinstance(terms, list):
        terms = [str(part).strip() for part in terms if str(part).strip()]
    else:
        terms = []

    alternatives = item.get("alternatives") or []
    if not isinstance(alternatives, list):
        alternatives = []
    alternatives = [
        re.sub(r"\s+", " ", str(value).strip())
        for value in alternatives[:2]
        if str(value).strip()
    ]

    chunks = item.get("chunks") or []
    if not isinstance(chunks, list):
        chunks = []
    chunks = [str(value).strip() for value in chunks if str(value).strip()]
    if len(chunks) < 2:
        chunks = default_chunks(en)

    difficulty = str(item.get("difficulty") or "intermediate").strip().lower()
    if difficulty not in VALID_DIFFICULTIES:
        difficulty = "intermediate"

    return {
        "category": str(item.get("category") or fallback_category).strip(),
        "difficulty": difficulty,
        "context_cn": str(item.get("context_cn") or "").strip(),
        "cn": cn,
        "en": en,
        "key_terms": ", ".join(terms[:6]),
        "note": str(item.get("note") or "").strip(),
        "alternatives_json": json.dumps(alternatives, ensure_ascii=False),
        "chunks_json": json.dumps(chunks, ensure_ascii=False),
    }


def generate_sqe_cards(source_text, source_label, category, valid_categories, logger=None):
    source_text = (source_text or "").strip()
    if not source_text:
        return []
    category_list = ", ".join(valid_categories)
    prompt = f"""You are an English coach for an automotive supplier quality engineer in China.
Create 4 concise workplace speaking-practice cards from the source below.

Return JSON only:
{{
  "cards": [
    {{
      "category": "{category}",
      "difficulty": "foundation|intermediate|advanced",
      "context_cn": "one short Chinese workplace context",
      "cn": "the Chinese speaking intention",
      "en": "natural professional spoken English",
      "key_terms": ["term 1", "term 2"],
      "note": "one short Chinese usage or interpretation tip",
      "alternatives": ["one optional natural English alternative"],
      "chunks": ["meaningful English chunk 1", "chunk 2"]
    }}
  ]
}}

Rules:
- Categories must be one of: {category_list}.
- Write language for meetings, supplier audits, factory visits, quality issues,
  8D discussions, interpreting, claims, or urgent containment.
- The English must sound natural when spoken, not like a formal email.
- Each English sentence should normally be 8-24 words.
- Do not include supplier names, report numbers, part numbers, amounts, or other identifiers.
- Preserve technical meaning. Do not invent process facts or corrective actions.
- Make the four cards cover different speaking intentions.
- Chunks must reconstruct the English sentence exactly when joined with spaces.

Source label: {source_label}
Source:
{source_text[:6000]}
"""
    raw = _call_ollama(prompt, timeout=150, num_predict=1600, logger=logger)
    parsed = _parse_json(raw)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("cards"), list):
        return []

    cards = []
    for item in parsed["cards"][:6]:
        card = _clean_card(item, category)
        if card and card["category"] in valid_categories:
            cards.append(card)
    return cards


__all__ = [
    "OLLAMA_MODEL",
    "VALID_RATINGS",
    "default_chunks",
    "generate_sqe_cards",
    "schedule_review",
]
