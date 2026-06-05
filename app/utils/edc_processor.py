import os
import re
import threading
import pdfplumber
from datetime import datetime

ONEDRIVE_FOLDER = r"D:\OneDrive - Piaggio & C. SPA\File di Chen De Feng - EDC reports"

_sync_state = {
    "running": False, "total": 0, "current": 0, "added": 0,
    "skipped": 0, "failed": 0, "percent": 0,
    "file": "", "message": "", "done": False, "error": "",
}
_sync_lock = threading.Lock()


def get_sync_state():
    with _sync_lock:
        return dict(_sync_state)


def _update_state(**kwargs):
    with _sync_lock:
        _sync_state.update(kwargs)


def parse_edc_pdf(file_path: str) -> dict | str | None:
    """
    解析单个 EDC PDF。
    返回 dict（成功）、"SKIP_NOT_REPORT"（非报告）、None（解析失败）
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            text = pdf.pages[0].extract_text() or ""
            for p in pdf.pages[1:]:
                text += "\n" + (p.extract_text() or "")
    except Exception as e:
        import traceback
        print(f"[PDF ERROR] {os.path.basename(file_path)}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None

    if "QUALITY REPORT" not in text.upper():
        return "SKIP_NOT_REPORT"

    def qf(pattern, content=text, default=""):
        m = re.search(pattern, content, re.I | re.M)
        return m.group(1).strip() if m else default

    # ── 1. 报告编号 ──────────────────────────────────────────
    no_m = re.search(r"[NΝ]\.?\s*(\d{9})(?!\d)", text)
    if no_m:
        report_no = no_m.group(1)
    else:
        fn_m = re.search(r"(\d{9})", os.path.basename(file_path))
        if not fn_m:
            print(f"[FAILED] {os.path.basename(file_path)}: no 9-digit report number found")
            return None
        report_no = fn_m.group(1)

    # ── 2. 分类 ──────────────────────────────────────────────
    classification = qf(r"QUALITY REPORT FOR\s+(.+?)(?:\n|$)").upper() or "UNKNOWN"

    # ── 3. 日期：只取标题行，跳过 End of deviation 行 ────────
    report_date = None
    for line in text.splitlines():
        if "end of deviation" in line.lower():
            continue
        dm = re.search(r"Date:\s*(\d{2}[./]\d{2}[./]\d{4})", line, re.I)
        if dm:
            try:
                report_date = datetime.strptime(
                    dm.group(1).replace("/", "."), "%d.%m.%Y"
                ).date()
            except ValueError:
                pass
            break

    # ── 4. 供应商 code + name ────────────────────────────────
    # 实际结构（pdfplumber 双列合并后）：
    #   行N:   'Supplier code:ITMD10814  Ref.:        Ditta'
    #   行N+1: 'Type Notice: EF          CHONGQING JIELI WHEEL MANUFACTURING'
    #   行N+2: 'Approval status: ...     CO., LTD.'
    sup_code = ""
    sup_name = ""
    lines = text.splitlines()

    for idx, line in enumerate(lines):
        if not re.search(r"Supplier\s*[Cc]ode", line, re.I):
            continue

        # 提取 code
        code_m = re.search(r"Supplier\s*[Cc]ode[.:]?\s*([A-Z0-9]+)", line, re.I)
        if code_m:
            sup_code = code_m.group(1).strip()

        # 检查 Ref./Rif. 后面是否有直接的公司名（非 Ditta 格式）
        ref_m = re.search(r"(?:Ref[.:]?|Rif[.:]?)\s*(.+)", line, re.I)
        raw = ref_m.group(1).strip() if ref_m else ""
        raw = re.sub(r"Supplier\s*[Cc]ode[.:]?\s*[A-Z0-9]+", "", raw, flags=re.I).strip()
        raw = re.sub(r"^\s*Ditta\s*$", "", raw, flags=re.I).strip()
        raw = raw.lstrip(":").lstrip(".").strip()

        if raw and len(raw) > 3:
            # 直接有公司名（非 Ditta 格式）
            sup_name = raw[:255]
        else:
            # Ditta 格式：从后续行的右列提取，可能跨多行
            # 右列内容在左列字段标签之后，格式：'字段: 值   右列内容'
            name_parts = []
            for ni in range(idx + 1, min(idx + 5, len(lines))):
                nl = lines[ni]
                # 跳过纯 Ditta 行
                if re.match(r"^\s*Ditta\s*$", nl, re.I):
                    continue
                # 取冒号+短值之后的大写内容（右列）
                m = re.search(r":\s*\S{0,20}\s+([A-Z][A-Z0-9\s\-.,&()/]+)$", nl)
                if not m:
                    # 无字段标签，整行就是右列内容
                    if nl.strip() and re.match(r"^[A-Z]", nl.strip()):
                        m_full = nl.strip()
                        if len(m_full) > 3:
                            name_parts.append(m_full)
                            if not re.search(r"\bLTD\.?$|\bINC\.?$|\bCO\.?\s*$", m_full):
                                break
                    continue
                part = m.group(1).strip()
                if not part:
                    continue
                name_parts.append(part)
                # 如果这行不是以 LTD/CO/INC 结尾，说明公司名完整了
                if not re.search(r"\bLTD\.?$|\bINC\.?$|\bCO\.?\s*$", part):
                    break

            full_name = " ".join(name_parts).strip()
            # 过滤掉只有 CO., LTD 这种残片
            if full_name and not re.match(r"^CO\.?,?\s*LTD", full_name, re.I):
                sup_name = full_name[:255]

        break

    # ── 5. 图号 / 零件名 ─────────────────────────────────────
    drawing   = qf(r"Drawing[.:]?\s*([\w\-/]+)")
    part_name = qf(r"Description[.:]?\s*(.+?)(?:\n|$)")
    part_name = re.sub(r"\s+\d{5,}.*$", "", part_name).strip()

    # ── 6. 数量 ──────────────────────────────────────────────
    rej_m = re.search(r"Rejected\s*Parts[.:]?\s*(\d+)", text, re.I)
    rejected_parts = int(rej_m.group(1)) if rej_m else 0

    rec_m = re.search(r"Received\s*Parts[.:]?\s*(\d[\d,]*)", text, re.I)
    received_parts = int(rec_m.group(1).replace(",", "")) if rec_m else 0

    # ── 7. 问题描述 removals（支持多种格式）─────────────────
    removals = ""

    # 格式 A：有 REMOVALS 关键字（MASS PRODUCTION 常见）
    rem_m = re.search(
        r"\bREMOVALS\b\s*\n(.+?)(?=\nSUPPLY\s+QUALITY|\Z)",
        text, re.I | re.DOTALL
    )
    if rem_m:
        removals = rem_m.group(1).strip()

    # 格式 B：Lot checked.:0 之后（INITIAL SAMPLE 常见）
    elif "Lot checked.:0" in text:
        after = text.split("Lot checked.:0", 1)[-1].strip()
        after = re.split(r"SUPPLY\s+QUALITY", after, flags=re.I)[0]
        removals = after.strip()

    # 格式 C：Lot check. + SAP编号 之后
    elif re.search(r"Lot check\.\s*\d+", text, re.I):
        after = re.split(r"Lot check\.\s*\d+", text, flags=re.I)[-1].strip()
        after = re.split(r"SUPPLY\s+QUALITY", after, flags=re.I)[0]
        removals = after.strip()

    # 格式 D：End of deviation Date 之后 + Lot checked
    elif "End of deviation Date:" in text:
        after = text.split("End of deviation Date:", 1)[-1]
        after = re.sub(r"^\s*[\d./]+", "", after)
        after = re.split(r"Lot checked", after, flags=re.I)[0]
        after = re.split(r"SUPPLY\s+QUALITY", after, flags=re.I)[0]
        removals = after.strip()

    # 去掉末尾 *** 分割线（保留分割线后的英文内容）
    # 注意：不截断，*** 只是视觉分隔符
    removals = re.split(r"\nSUPPLY\s+QUALITY", removals, flags=re.I)[0].strip()

    return {
        "report_no":      report_no,
        "classification": classification[:100],
        "report_date":    report_date,
        "supplier_code":  sup_code[:64],
        "supplier_name":  sup_name[:255],
        "drawing":        drawing[:128],
        "part_name":      part_name[:255],
        "rejected_parts": rejected_parts,
        "received_parts": received_parts,
        "removals":       removals,
        "file_path":      file_path,
    }


def _sync_worker(app):
    with app.app_context():
        from app.models import EDCReport
        from app.extensions import db

        try:
            # ── 只处理数据库里还没有的报告编号 ────────────────
            existing_nos = set(
                row[0] for row in db.session.query(EDCReport.report_no).all()
            )

            # 只取 9位数字命名的 PDF（正规报告文件名格式）
            all_pdfs = [
                f for f in os.listdir(ONEDRIVE_FOLDER)
                if f.lower().endswith(".pdf")
                and re.match(r"^\d{9}(-\d+)?$", os.path.splitext(f)[0])
            ]

            # 过滤掉已存在的
            new_pdfs = [
                f for f in all_pdfs
                if re.search(r"\d{9}", f).group(0) not in existing_nos
            ]

            total   = len(new_pdfs)
            added   = 0
            skipped = 0
            failed  = 0

            _update_state(
                total=total, current=0, added=0, skipped=0, failed=0,
                percent=0, file="", message="", done=False, error=""
            )

            if total == 0:
                _update_state(running=False, done=True,
                              message="✅ 已是最新，没有新报告需要导入")
                return

            BATCH_SIZE = 50
            batch      = []
            batch_nos  = set()

            for i, filename in enumerate(new_pdfs, 1):
                full_path = os.path.join(ONEDRIVE_FOLDER, filename)

                _update_state(
                    current=i,
                    percent=round(i / total * 100, 1),
                    file=filename,
                    added=added,
                    skipped=skipped,
                    failed=failed,
                )

                result = parse_edc_pdf(full_path)

                if result == "SKIP_NOT_REPORT":
                    skipped += 1
                    continue

                if not result or not isinstance(result, dict):
                    failed += 1
                    continue

                rno = result["report_no"]
                if rno in batch_nos or rno in existing_nos:
                    skipped += 1
                    continue

                batch.append(result)
                batch_nos.add(rno)
                added += 1

                # 批量提交
                if len(batch) >= BATCH_SIZE or i == total:
                    if batch:
                        try:
                            db.session.bulk_insert_mappings(EDCReport, batch)
                            db.session.commit()
                            for d in batch:
                                existing_nos.add(d["report_no"])
                        except Exception as e:
                            db.session.rollback()
                            # 批量失败 → 逐条重试
                            success_in_batch = 0
                            for d in batch:
                                try:
                                    db.session.merge(EDCReport(**d))
                                    db.session.commit()
                                    existing_nos.add(d["report_no"])
                                    success_in_batch += 1
                                except Exception:
                                    db.session.rollback()
                                    added  -= 1
                                    failed += 1
                        batch     = []
                        batch_nos = set()

            _update_state(
                running=False, done=True,
                added=added, skipped=skipped, failed=failed,
                message=f"✅ 同步完成！新增 {added} 条，跳过 {skipped} 条，失败 {failed} 条",
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            _update_state(running=False, done=True, error=str(e))


def start_sync_background(app):
    with _sync_lock:
        if _sync_state["running"]:
            return False
        _sync_state.update({
            "running": True, "done": False, "error": "",
            "total": 0, "current": 0, "added": 0,
            "skipped": 0, "failed": 0, "percent": 0,
            "file": "", "message": "正在准备...",
        })

    app_obj = app._get_current_object() if hasattr(app, "_get_current_object") else app
    threading.Thread(target=_sync_worker, args=(app_obj,), daemon=True).start()
    return True