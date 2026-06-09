from flask import render_template, request, redirect, url_for, flash, send_file, abort, current_app, jsonify
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import uuid
import time
import threading
import subprocess
import hashlib
from pathlib import Path

from . import tr_bp
from ...extensions import db
from ...models import TroubleReport, TRDocument, Supplier

from ...ai_helper import summarize_issue

# ──────────────────────────────────────────────────────────
# EDC 缓存与预下载状态
# ──────────────────────────────────────────────────────────
_edc_cache = {"data": None, "ts": 0}
_CACHE_TTL = 300

_predownload_lock = threading.Lock()
_predownloading = set()
_predownloaded  = set()

_attach_sync_lock = threading.Lock()
_attach_syncing_trs = set()

_scheduler_started = False
_scheduler_lock    = threading.Lock()
_SCHEDULE_INTERVAL = 3600

ALLOWED_8D_STATUS = {"NOT_REQUIRED", "NOT_RECEIVED", "RECEIVED_REJECT", "RECEIVED_PASS"}

EIGHTD_SEARCH_MAP = {
    "NOT_REQUIRED": "不要求",
    "NOT_RECEIVED": "未收到",
    "RECEIVED_REJECT": "reject",
    "RECEIVED_PASS": "pass",
}

DOC_TYPES = {
    "quality_report": "Quality Report",
    "test_report": "Test Report",
    "8d_report": "8D Report",
    "photo": "Photos",
    "capa": "CAPA",
    "email": "Email",
    "debit_note": "Debit Note",
    "other": "Other",
}

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "jpg", "jpeg", "png", "gif", "bmp", "webp",
    "zip", "rar", "msg", "eml", "txt"
}

MIME_TO_EXT = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xls",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/pdf": "pdf",
    "image/jpeg": "jpg", "image/png": "png", "image/gif": "gif",
    "image/bmp": "bmp", "image/webp": "webp",
    "application/zip": "zip", "application/x-zip-compressed": "zip",
    "application/x-rar-compressed": "rar",
    "application/vnd.ms-outlook": "msg", "message/rfc822": "eml",
    "text/plain": "txt",
}

EXT_TO_DOC_TYPE = {
    "jpg": "photo", "jpeg": "photo", "png": "photo",
    "gif": "photo", "bmp": "photo", "webp": "photo",
    "msg": "email", "eml": "email",
    "doc": "other", "docx": "other", "xls": "other", "xlsx": "other",
    "ppt": "other", "pptx": "other", "zip": "other", "rar": "other", "txt": "other",
}

EXT_TO_MIME = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
    "bmp": "image/bmp", "webp": "image/webp", "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "zip": "application/zip", "rar": "application/x-rar-compressed",
    "msg": "application/vnd.ms-outlook", "eml": "message/rfc822", "txt": "text/plain",
}

OFFICE_EXTS = {"doc", "docx", "xls", "xlsx", "ppt", "pptx"}
PREVIEW_CACHE_DIR = "preview_cache"

LIBREOFFICE_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice", "/usr/bin/libreoffice",
]


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def guess_ext(filename, mimetype):
    ext = ""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[1].lower().strip()
    if not ext:
        ext = MIME_TO_EXT.get((mimetype or "").lower().strip(), "")
    return ext


# ── Office → PDF 转换 ──

def _find_soffice():
    for p in LIBREOFFICE_PATHS:
        if os.path.exists(p):
            return p
    return None

def _convert_to_pdf(src_path, cache_dir, logger=None):
    src = Path(src_path)
    if not src.exists():
        return None
    key = hashlib.md5(f"{src}_{src.stat().st_size}_{src.stat().st_mtime}".encode()).hexdigest()
    cached_pdf = Path(cache_dir) / f"{key}.pdf"
    if cached_pdf.exists():
        return str(cached_pdf)
    soffice = _find_soffice()
    if not soffice:
        return None
    os.makedirs(cache_dir, exist_ok=True)
    try:
        if logger:
            logger.info(f"[Preview] converting {src.name}...")
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf:calc_pdf_Export:{'SinglePageSheets':{'type':1,'value':true}}", "--outdir", str(cache_dir), str(src)],
            timeout=60, capture_output=True, text=True,
        )
        if result.returncode != 0:
            return None
        generated = Path(cache_dir) / (src.stem + ".pdf")
        if generated.exists():
            generated.rename(cached_pdf)
            return str(cached_pdf)
        return None
    except Exception:
        return None


# ── OneDrive 文件读取 ──

def _read_file_with_timeout(file_path, timeout=60):
    holder = {"data": None, "error": None}
    done = threading.Event()
    def _read():
        try:
            with open(str(file_path), "rb") as f:
                holder["data"] = f.read()
        except Exception as e:
            holder["error"] = str(e)
        finally:
            done.set()
    t = threading.Thread(target=_read, daemon=True)
    t.start()
    if not done.wait(timeout=timeout):
        return None, f"Download timeout (>{timeout}s)"
    return holder["data"], holder["error"]

def _is_cloud_placeholder(file_path):
    try:
        st = os.stat(str(file_path))
        return bool(getattr(st, "st_file_attributes", 0) & 0x00400000)
    except Exception:
        return False


# ── 后台预下载 + 定时扫描 ──

def _predownload_pdf(edc_no, onedrive_path, logger=None):
    with _predownload_lock:
        if edc_no in _predownloading or edc_no in _predownloaded:
            return
        _predownloading.add(edc_no)
    try:
        root = Path(onedrive_path)
        if not root.exists(): return
        pdf_path = None
        for p in root.rglob(f"*{edc_no}*.pdf"):
            pdf_path = p; break
        if not pdf_path: return
        with open(str(pdf_path), "rb") as f:
            f.read()
        if logger: logger.info(f"[EDC predownload] OK {edc_no}")
        with _predownload_lock:
            _predownloading.discard(edc_no); _predownloaded.add(edc_no)
    except Exception as e:
        if logger: logger.warning(f"[EDC predownload] FAIL {edc_no}: {e}")
        with _predownload_lock:
            _predownloading.discard(edc_no)


def _scan_outlook_silent(app):
    with app.app_context():
        try:
            import re, win32com.client, pythoncom
            pythoncom.CoInitialize()
            folder_name = app.config.get("EDC_OUTLOOK_FOLDER", "FPVT-EDC Ass.")
            onedrive_path = app.config.get("EDC_ONEDRIVE_PATH", "")
            outlook = win32com.client.Dispatch("Outlook.Application")
            ns = outlook.GetNamespace("MAPI")
            def find_folder(parent, name):
                try:
                    for folder in parent.Folders:
                        if folder.Name.strip() == name.strip(): return folder
                        sub = find_folder(folder, name)
                        if sub: return sub
                except Exception: pass
                return None
            target = None
            for store in ns.Stores:
                try:
                    target = find_folder(store.GetRootFolder(), folder_name)
                    if target: break
                except Exception: continue
            if not target or not onedrive_path: return
            items = target.Items; items.Sort("[ReceivedTime]", True)
            existing_trs = {tr.tr_no.replace("TR-EDC-", "") for tr in TroubleReport.query.filter(TroubleReport.tr_no.like("TR-EDC-%")).all()}
            edc_nos = []
            for i, item in enumerate(items):
                if i >= int(app.config.get("EDC_SCAN_LIMIT", 200)): break
                try:
                    m = re.search(r"\b(\d{8,12})\b", item.Subject or "")
                    if m and m.group(1) not in existing_trs:
                        edc_nos.append(m.group(1))
                except Exception: continue
            for edc_no in edc_nos[:30]:
                threading.Thread(target=_predownload_pdf, args=(edc_no, onedrive_path, app.logger), daemon=True).start()
        except Exception: pass


def _start_scheduler_if_needed(app):
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started: return
        _scheduler_started = True
    def _run():
        time.sleep(60)
        while True:
            try: _scan_outlook_silent(app)
            except Exception: pass
            time.sleep(_SCHEDULE_INTERVAL)
    threading.Thread(target=_run, daemon=True, name="edc-scheduler").start()
    app.logger.info(f"[EDC] Background scheduler started")
    soffice = _find_soffice()
    if soffice: app.logger.info(f"[Preview] LibreOffice at {soffice}")


# ── 自动导入 EDC 附件 ──
def _generate_issue_summary(app, tr_id):
    """后台用 AI 提取并转述 TR 的问题描述"""
    with app.app_context():
        try:
            tr = TroubleReport.query.get(tr_id)
            if not tr or not tr.issue_description:
                return

            summary = summarize_issue(tr.issue_description, logger=app.logger)
            if summary:
                tr.issue_summary = summary
                db.session.commit()
                app.logger.info(f"[AI] TR {tr.tr_no} summary saved")
        except Exception as e:
            app.logger.warning(f"[AI] summary failed for TR {tr_id}: {e}")


def _auto_import_edc_attachments(app, tr_id, _retry_count=0):
    import re
    MAX_RETRIES = 3; RETRY_DELAY = 30
    if _retry_count == 0:
        with _attach_sync_lock:
            if tr_id in _attach_syncing_trs:
                app.logger.info(f"[EDC attach] TR {tr_id} already syncing, skip"); return
            _attach_syncing_trs.add(tr_id)
    will_retry = False
    with app.app_context():
        try:
            tr = TroubleReport.query.get(tr_id)
            if not tr: return
            m = re.match(r"TR-EDC-(\d+)", tr.tr_no)
            if not m: return
            edc_no = m.group(1)
            onedrive_path = app.config.get("EDC_ONEDRIVE_PATH", "")
            if not onedrive_path: return
            root = Path(onedrive_path)
            if not root.exists(): return

            edc_folder = None
            for d in root.rglob(f"*{edc_no}*"):
                if d.is_dir(): edc_folder = d.resolve(); break
            if not edc_folder: return

            main_pdf_names = set()
            for p in root.rglob(f"*{edc_no}*.pdf"):
                if p.resolve().parent != edc_folder:
                    main_pdf_names.add(p.name.lower())

            seen_paths = set(); candidates = []
            for f in edc_folder.rglob("*"):
                if not f.is_file(): continue
                f_resolved = f.resolve()
                if f_resolved in seen_paths: continue
                seen_paths.add(f_resolved)
                ext = f.suffix.lower().lstrip(".")
                if ext not in ALLOWED_EXTENSIONS: continue
                if ext == "pdf" and f.name.lower() in main_pdf_names: continue
                candidates.append(f_resolved)

            if not candidates: return

            tr_dir = os.path.join("tr_docs", secure_filename(tr.tr_no))
            full_dir = os.path.join(app.config["UPLOAD_DIR"], tr_dir)
            os.makedirs(full_dir, exist_ok=True)
            existing = {doc.original_name for doc in tr.documents}
            to_process = [s for s in candidates if s.name not in existing]
            if not to_process: return

            def _try_read(p):
                return _read_file_with_timeout(p, timeout=30 if _is_cloud_placeholder(p) else 10)

            results = {}
            with ThreadPoolExecutor(max_workers=5) as executor:
                fmap = {executor.submit(_try_read, s): s for s in to_process}
                for future in as_completed(fmap):
                    src = fmap[future]
                    try: results[src] = future.result()
                    except Exception as e: results[src] = (None, str(e))

            imported = 0; failed = 0; still_downloading = 0
            for src, (data, err) in results.items():
                if err or not data:
                    if err and "timeout" in err.lower(): still_downloading += 1
                    else: failed += 1
                    continue
                if TRDocument.query.filter_by(tr_id=tr.id, original_name=src.name).first(): continue
                ext = src.suffix.lower().lstrip(".")
                stored_name = f"{uuid.uuid4().hex}.{ext}"
                file_path = os.path.join(full_dir, stored_name)
                try:
                    with open(file_path, "wb") as f: f.write(data)
                except Exception: failed += 1; continue
                doc_type = EXT_TO_DOC_TYPE.get(ext, "other")
                if ext == "pdf":
                    nl = src.name.lower()
                    if "8d" in nl: doc_type = "8d_report"
                    elif "test" in nl or "report" in nl: doc_type = "test_report"
                    elif "capa" in nl: doc_type = "capa"
                    else: doc_type = "test_report"
                db.session.add(TRDocument(
                    tr_id=tr.id, doc_type=doc_type, title=src.stem,
                    original_name=src.name, stored_name=stored_name,
                    rel_path=os.path.join(tr_dir, stored_name),
                    mime=EXT_TO_MIME.get(ext, "application/octet-stream"),
                    size=len(data), remark="Auto-imported from EDC folder",
                ))
                imported += 1
            db.session.commit()
            app.logger.info(f"[EDC attach] TR {tr.tr_no}: imported={imported}, still_downloading={still_downloading}, failed={failed}")

            if still_downloading > 0 and _retry_count < MAX_RETRIES:
                will_retry = True
                def _retry():
                    time.sleep(RETRY_DELAY)
                    _auto_import_edc_attachments(app, tr_id, _retry_count + 1)
                threading.Thread(target=_retry, daemon=True).start()
        except Exception as e:
            app.logger.warning(f"[EDC attach] failed for TR {tr_id}: {e}")
        finally:
            if not will_retry:
                with _attach_sync_lock:
                    _attach_syncing_trs.discard(tr_id)


# ──────────────────────────────────────────────────────────
# 辅助：从表单读取 debit 字段
# ──────────────────────────────────────────────────────────
def _read_debit_from_form():
    debit_ref = (request.form.get("debit_ref") or "").strip() or None
    debit_date = (request.form.get("debit_date") or "").strip() or None
    debit_currency = (request.form.get("debit_currency") or "EUR").strip()
    raw_amount = (request.form.get("debit_amount") or "").strip()
    debit_amount = None
    if raw_amount:
        try:
            debit_amount = float(raw_amount.replace(",", ""))
        except (ValueError, TypeError):
            pass
    return debit_ref, debit_amount, debit_currency, debit_date


# ──────────────────────────────────────────────────────────
# 列表 / 新建 / 编辑 / 删除
# ──────────────────────────────────────────────────────────

@tr_bp.route("/", methods=["GET"])
def index():
    _start_scheduler_if_needed(current_app._get_current_object())

    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = TroubleReport.query

    if q:
        like = f"%{q}%"
        extra_8d_status = []
        for k, v in EIGHTD_SEARCH_MAP.items():
            if v in q.lower():
                extra_8d_status.append(k)

        query = query.filter(
            or_(
                TroubleReport.tr_no.ilike(like),
                TroubleReport.supplier_name.ilike(like),
                TroubleReport.part_number.ilike(like),
                TroubleReport.part_name.ilike(like),
                TroubleReport.issue_description.ilike(like),
                TroubleReport.severity.ilike(like),
                TroubleReport.eight_d.ilike(like),
                TroubleReport.eight_d_status.ilike(like),
                TroubleReport.eight_d_status.in_(extra_8d_status) if extra_8d_status else False,
                TroubleReport.status.ilike(like),
                TroubleReport.remark.ilike(like),
                TroubleReport.debit_ref.ilike(like),
            )
        )

    query = query.order_by(TroubleReport.is_pinned.desc(), TroubleReport.created_at.desc(), TroubleReport.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 全局统计（不受分页影响）
    from sqlalchemy import func, case
    stats = db.session.query(
        func.count(TroubleReport.id).label('total'),
        func.sum(case((func.lower(TroubleReport.status).in_(['closed', 'done', 'completed']), 1), else_=0)).label(
            'closed'),
        func.sum(case((TroubleReport.eight_d_status == 'NOT_RECEIVED', 1), else_=0)).label('pending_8d'),
    ).first()
    total = stats.total or 0
    closed = int(stats.closed or 0)
    ongoing = total - closed
    pending_8d = int(stats.pending_8d or 0)

    return render_template("tr/index.html", trs=pagination.items, pagination=pagination,
                           q=q, per_page=per_page,
                           stat_ongoing=ongoing, stat_closed=closed, stat_8d=pending_8d)


@tr_bp.route("/new", methods=["GET", "POST"])
def new_tr():
    if request.method == "POST":
        tr_no = (request.form.get("tr_no") or "").strip()
        supplier_name = (request.form.get("supplier_name") or "").strip()
        part_number = (request.form.get("part_number") or "").strip() or None
        part_name = (request.form.get("part_name") or "").strip() or None
        issue_description = (request.form.get("issue_description") or "").strip()
        severity = (request.form.get("severity") or "").strip() or None
        eight_d = (request.form.get("eight_d") or "").strip() or None
        eight_d_status = (request.form.get("eight_d_status") or "NOT_REQUIRED").strip()
        if eight_d_status not in ALLOWED_8D_STATUS: eight_d_status = "NOT_REQUIRED"
        status = (request.form.get("status") or "Open").strip() or "Open"
        remark = (request.form.get("remark") or "").strip() or None
        debit_ref, debit_amount, debit_currency, debit_date = _read_debit_from_form()

        suppliers = Supplier.query.order_by(Supplier.code).all()

        if not tr_no:
            flash("TR No. cannot be empty", "error")
            return render_template("tr/form.html", mode="new", tr=None, suppliers=suppliers)
        if not supplier_name:
            flash("Supplier Name cannot be empty", "error")
            return render_template("tr/form.html", mode="new", tr=None, suppliers=suppliers)
        if not issue_description:
            flash("Issue Description cannot be empty", "error")
            return render_template("tr/form.html", mode="new", tr=None, suppliers=suppliers)
        if TroubleReport.query.filter_by(tr_no=tr_no).first():
            flash(f"TR No. already exists: {tr_no}", "error")
            return render_template("tr/form.html", mode="new", tr=None, suppliers=suppliers)

        tr = TroubleReport(
            tr_no=tr_no, supplier_code="N/A", supplier_name=supplier_name,
            part_number=part_number, part_name=part_name,
            issue_description=issue_description, severity=severity,
            eight_d=eight_d, eight_d_status=eight_d_status,
            status=status, remark=remark,
            debit_ref=debit_ref, debit_amount=debit_amount,
            debit_currency=debit_currency, debit_date=debit_date,
            lot_number=(request.form.get("lot_number") or "").strip() or None,
        )
        db.session.add(tr)
        db.session.commit()
        _edc_cache["data"] = None

        if tr_no.startswith("TR-EDC-"):
            threading.Thread(target=_auto_import_edc_attachments,
                                   args=(current_app._get_current_object(), tr.id), daemon=True).start()
                  # ↓ 新增这一段：AI 提取问题摘要
            threading.Thread(target=_generate_issue_summary,
                                   args=(current_app._get_current_object(), tr.id), daemon=True).start()
            flash("✅ TR created. Importing attachments + generating AI summary...", "success")
        else:
            flash("✅ TR created successfully", "success")
            next_url = request.form.get("next") or request.args.get("next") or url_for("tr.index")
            return redirect(next_url)

    suppliers = Supplier.query.order_by(Supplier.code).all()
    next_url = request.args.get("next", "")
    return render_template("tr/form.html", mode="new", tr=None, suppliers=suppliers, next_url=next_url)


@tr_bp.route("/<int:tr_id>/edit", methods=["GET", "POST"])
def edit_tr(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)

    if request.method == "POST":
        tr_no = (request.form.get("tr_no") or "").strip()
        supplier_name = (request.form.get("supplier_name") or "").strip()
        part_number = (request.form.get("part_number") or "").strip() or None
        part_name = (request.form.get("part_name") or "").strip() or None
        issue_description = (request.form.get("issue_description") or "").strip()
        severity = (request.form.get("severity") or "").strip() or None
        eight_d = (request.form.get("eight_d") or "").strip() or None
        eight_d_status = (request.form.get("eight_d_status") or "NOT_REQUIRED").strip()
        if eight_d_status not in ALLOWED_8D_STATUS: eight_d_status = "NOT_REQUIRED"
        status = (request.form.get("status") or "Open").strip() or "Open"
        remark = (request.form.get("remark") or "").strip() or None
        debit_ref, debit_amount, debit_currency, debit_date = _read_debit_from_form()

        documents = tr.documents.order_by(TRDocument.created_at.desc()).all()
        suppliers = Supplier.query.order_by(Supplier.code).all()

        if not tr_no:
            flash("TR No. cannot be empty", "error")
            return render_template("tr/form.html", mode="edit", tr=tr, documents=documents, doc_types=DOC_TYPES, suppliers=suppliers)
        if not supplier_name:
            flash("Supplier Name cannot be empty", "error")
            return render_template("tr/form.html", mode="edit", tr=tr, documents=documents, doc_types=DOC_TYPES, suppliers=suppliers)
        if not issue_description:
            flash("Issue Description cannot be empty", "error")
            return render_template("tr/form.html", mode="edit", tr=tr, documents=documents, doc_types=DOC_TYPES, suppliers=suppliers)
        if tr_no != tr.tr_no and TroubleReport.query.filter_by(tr_no=tr_no).first():
            flash(f"TR No. already exists: {tr_no}", "error")
            return render_template("tr/form.html", mode="edit", tr=tr, documents=documents, doc_types=DOC_TYPES, suppliers=suppliers)

        tr.tr_no = tr_no; tr.supplier_name = supplier_name
        tr.part_number = part_number; tr.part_name = part_name
        tr.issue_description = issue_description; tr.severity = severity
        tr.eight_d = eight_d; tr.eight_d_status = eight_d_status
        tr.status = status; tr.remark = remark
        tr.debit_ref = debit_ref; tr.debit_amount = debit_amount
        tr.debit_currency = debit_currency; tr.debit_date = debit_date

        db.session.commit()
        threading.Thread(target=_generate_issue_summary,
                        args=(current_app._get_current_object(), tr.id), daemon=True).start()
        flash("✅ TR updated successfully", "success")
        next_url = request.form.get("next") or request.args.get("next") or url_for("tr.index")
        return redirect(next_url)

    documents = tr.documents.order_by(TRDocument.created_at.desc()).all()
    suppliers = Supplier.query.order_by(Supplier.code).all()
    next_url = request.args.get("next", "")
    return render_template("tr/form.html", mode="edit", tr=tr, documents=documents, doc_types=DOC_TYPES,
                           suppliers=suppliers, next_url=next_url)


@tr_bp.route("/<int:tr_id>/delete", methods=["POST"])
def delete_tr(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    for doc in tr.documents:
        fp = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
        if os.path.exists(fp):
            try: os.remove(fp)
            except OSError: pass
    db.session.delete(tr); db.session.commit()
    flash("✅ TR deleted successfully", "success")
    next_url = request.form.get("next") or request.args.get("next") or url_for("tr.index")
    return redirect(next_url)


# ── 文档管理 ──

@tr_bp.route("/<int:tr_id>/documents/upload", methods=["POST"])
def upload_document(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    if "file" not in request.files:
        flash("❌ No file selected", "error"); return redirect(url_for("tr.edit_tr", tr_id=tr_id))
    file = request.files["file"]
    if not file or file.filename == "":
        flash("❌ No file selected", "error"); return redirect(url_for("tr.edit_tr", tr_id=tr_id))
    raw_name = (file.filename or "").strip()
    if not allowed_file(raw_name):
        flash(f"❌ Unsupported format", "error"); return redirect(url_for("tr.edit_tr", tr_id=tr_id))
    doc_type = request.form.get("doc_type", "other")
    title = (request.form.get("title") or "").strip() or raw_name
    remark = (request.form.get("remark") or "").strip() or None
    ext = guess_ext(raw_name, file.mimetype)
    if not ext:
        flash("❌ Cannot recognize file extension", "error"); return redirect(url_for("tr.edit_tr", tr_id=tr_id))
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    tr_dir = os.path.join("tr_docs", secure_filename(tr.tr_no))
    full_dir = os.path.join(current_app.config["UPLOAD_DIR"], tr_dir)
    os.makedirs(full_dir, exist_ok=True)
    file_path = os.path.join(full_dir, stored_name)
    file.save(file_path)
    db.session.add(TRDocument(
        tr_id=tr.id, doc_type=doc_type, title=title,
        original_name=raw_name, stored_name=stored_name,
        rel_path=os.path.join(tr_dir, stored_name),
        mime=file.mimetype, size=os.path.getsize(file_path), remark=remark,
    ))
    db.session.commit()

    if doc_type == "8d_report":
        threading.Thread(
            target=_extract_8d_for_tr,
            args=(current_app._get_current_object(), tr.id),
            daemon=True
        ).start()
    flash(f"✅ Document uploaded: {title}", "success")
    return redirect(url_for("tr.edit_tr", tr_id=tr_id))


@tr_bp.route("/<int:tr_id>/documents/<int:doc_id>/view")
def view_document(tr_id, doc_id):
    TroubleReport.query.get_or_404(tr_id)
    doc = TRDocument.query.filter_by(id=doc_id, tr_id=tr_id).first_or_404()
    file_path = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
    if not os.path.exists(file_path): abort(404)
    from flask import make_response
    ext = doc.original_name.rsplit(".", 1)[1].lower() if doc.original_name and "." in doc.original_name else ""
    if ext in OFFICE_EXTS:
        cache_dir = os.path.join(current_app.config["UPLOAD_DIR"], PREVIEW_CACHE_DIR)
        pdf_path = _convert_to_pdf(file_path, cache_dir, current_app.logger)
        if pdf_path:
            resp = make_response(send_file(pdf_path, mimetype="application/pdf"))
            resp.headers['Content-Disposition'] = f'inline; filename="{doc.original_name}.pdf"'
            return resp
        return send_file(file_path, as_attachment=True, download_name=doc.original_name, mimetype=doc.mime)
    resp = make_response(send_file(file_path, mimetype=doc.mime or 'application/octet-stream'))
    resp.headers['Content-Disposition'] = f'inline; filename="{doc.original_name}"'
    return resp


@tr_bp.route("/<int:tr_id>/documents/<int:doc_id>/download")
def download_document(tr_id, doc_id):
    TroubleReport.query.get_or_404(tr_id)
    doc = TRDocument.query.filter_by(id=doc_id, tr_id=tr_id).first_or_404()
    file_path = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
    if not os.path.exists(file_path): abort(404)
    return send_file(file_path, as_attachment=True, download_name=doc.original_name, mimetype=doc.mime)


@tr_bp.route("/<int:tr_id>/documents/<int:doc_id>/delete", methods=["POST"])
def delete_document(tr_id, doc_id):
    TroubleReport.query.get_or_404(tr_id)
    doc = TRDocument.query.filter_by(id=doc_id, tr_id=tr_id).first_or_404()
    fp = os.path.join(current_app.config["UPLOAD_DIR"], doc.rel_path)
    if os.path.exists(fp):
        try: os.remove(fp)
        except OSError: pass
    db.session.delete(doc); db.session.commit()
    flash(f"✅ Document deleted: {doc.title}", "success")
    return redirect(url_for("tr.edit_tr", tr_id=tr_id))


@tr_bp.route("/<int:tr_id>/documents/panel", methods=["GET"])
def documents_panel(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    documents = tr.documents.order_by(TRDocument.created_at.desc()).all()
    return render_template("tr/_documents_panel.html", tr=tr, documents=documents, doc_types=DOC_TYPES)


@tr_bp.route("/<int:tr_id>/reimport-edc-attachments", methods=["POST"])
def reimport_edc_attachments(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    if not tr.tr_no.startswith("TR-EDC-"):
        flash("❌ Not an EDC TR", "error"); return redirect(url_for("tr.edit_tr", tr_id=tr_id))
    with _attach_sync_lock:
        if tr_id in _attach_syncing_trs:
            flash("⏳ 正在同步中，请耐心等待...", "info"); return redirect(url_for("tr.edit_tr", tr_id=tr_id))
    threading.Thread(target=_auto_import_edc_attachments, args=(current_app._get_current_object(), tr.id), daemon=True).start()
    flash("✅ Syncing EDC attachments in background...", "success")
    return redirect(url_for("tr.edit_tr", tr_id=tr_id))


# ── EDC 导入路由 ──

@tr_bp.route("/edc-inbox", methods=["POST"])
def edc_inbox():
    import re
    _start_scheduler_if_needed(current_app._get_current_object())
    folder_name = current_app.config.get("EDC_OUTLOOK_FOLDER", "FPVT-EDC Ass.")
    force = (request.get_json(silent=True) or {}).get("force", False)
    if not force and _edc_cache["data"] and (time.time() - _edc_cache["ts"]) < _CACHE_TTL:
        cached = dict(_edc_cache["data"]); cached["from_cache"] = True; return jsonify(cached)
    try:
        import win32com.client, pythoncom; pythoncom.CoInitialize()
    except ImportError:
        return jsonify({"ok": False, "error": "pywin32 not installed"}), 500
    try:
        outlook = win32com.client.Dispatch("Outlook.Application"); ns = outlook.GetNamespace("MAPI")
    except Exception as e:
        return jsonify({"ok": False, "error": f"Cannot connect to Outlook: {e}"}), 500

    def find_folder(parent, name):
        try:
            for folder in parent.Folders:
                if folder.Name.strip() == name.strip(): return folder
                sub = find_folder(folder, name)
                if sub: return sub
        except Exception: pass
        return None

    target = None
    for store in ns.Stores:
        try:
            target = find_folder(store.GetRootFolder(), folder_name)
            if target: break
        except Exception: continue
    if not target:
        return jsonify({"ok": False, "error": f"Outlook folder not found: '{folder_name}'"}), 404

    items = target.Items; items.Sort("[ReceivedTime]", True)
    existing_trs = {tr.tr_no.replace("TR-EDC-", ""): tr.id for tr in TroubleReport.query.filter(TroubleReport.tr_no.like("TR-EDC-%")).all()}
    emails = []; max_scan = int(current_app.config.get("EDC_SCAN_LIMIT", 200))
    for i, item in enumerate(items):
        if i >= max_scan: break
        try:
            subject = item.Subject or ""
            m = re.search(r"\b(\d{8,12})\b", subject)
            edc_no = m.group(1) if m else ""
            if not edc_no:
                m = re.search(r"EDC\s*No[.:]?\s*([0-9]{6,12})", item.Body or "", re.IGNORECASE)
                edc_no = m.group(1) if m else ""
            if not edc_no: continue
            tr_id_val = existing_trs.get(edc_no)
            try: recv_time = item.ReceivedTime.strftime("%Y-%m-%d %H:%M")
            except Exception: recv_time = ""
            if tr_id_val:
                emails.append({"edc_no": edc_no, "subject": subject, "received_at": recv_time, "edc_type": "", "result": "", "supplier": "", "material": "", "is_read": True, "already_has_tr": True, "tr_id": tr_id_val, "pdf_ready": None})
                continue
            body = item.Body or ""
            def grab(pattern, text=body):
                mm = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                return mm.group(1).strip() if mm else ""
            with _predownload_lock: pdf_ready = edc_no in _predownloaded
            emails.append({"edc_no": edc_no, "subject": subject, "received_at": recv_time, "edc_type": grab(r"Type[.:]?\s*(\w+)"), "result": grab(r"Result[.:]?\s*([^\n\r]+)"), "supplier": grab(r"Supplier[.:]?\s*([^\n\r]+)"), "material": grab(r"Material[.:]?\s*([^\n\r]+)"), "is_read": bool(item.UnRead == False), "already_has_tr": False, "tr_id": None, "pdf_ready": pdf_ready})
        except Exception: continue

    from collections import Counter
    edc_counts = Counter(e["edc_no"] for e in emails)
    duplicates = {k: v for k, v in edc_counts.items() if v > 1}
    current_app.logger.info(f"[EDC] {len(emails)} emails, {len(edc_counts)} unique")
    if duplicates: current_app.logger.info(f"[EDC] Duplicates: {duplicates}")

    result = {"ok": True, "emails": emails, "count": len(emails), "folder": folder_name, "from_cache": False}
    _edc_cache["data"] = result; _edc_cache["ts"] = time.time()

    onedrive_path = current_app.config.get("EDC_ONEDRIVE_PATH", "")
    if onedrive_path:
        launched = 0
        for e in [e["edc_no"] for e in emails if not e["already_has_tr"]][:20]:
            with _predownload_lock:
                if e in _predownloading or e in _predownloaded: continue
            threading.Thread(target=_predownload_pdf, args=(e, onedrive_path, current_app.logger), daemon=True).start()
            launched += 1
        if launched: current_app.logger.info(f"[EDC] Pre-downloading {launched} PDFs")
    return jsonify(result)


@tr_bp.route("/import-edc-no", methods=["POST"])
def import_edc_no():
    import re, io
    data = request.get_json(silent=True) or {}
    edc_no = str(data.get("edc_no", "")).strip()
    if not edc_no: return jsonify({"ok": False, "error": "EDC No. is required"}), 400
    onedrive_path = current_app.config.get("EDC_ONEDRIVE_PATH", "")
    if not onedrive_path: return jsonify({"ok": False, "error": "EDC_ONEDRIVE_PATH not set"}), 500
    root = Path(onedrive_path)
    if not root.exists(): return jsonify({"ok": False, "error": f"Path does not exist: {root}"}), 500
    pdf_path = None
    for p in root.rglob(f"*{edc_no}*.pdf"):
        pdf_path = p; break
    if not pdf_path:
        for p in root.rglob("*.pdf"):
            if edc_no.lower() in p.name.lower(): pdf_path = p; break
    if not pdf_path:
        return jsonify({"ok": False, "error": f"No PDF found for EDC {edc_no}", "searched_in": str(root)}), 404
    try:
        import pdfplumber
    except ImportError:
        return jsonify({"ok": False, "error": "Run: pip install pdfplumber"}), 500
    pdf_bytes, err = _read_file_with_timeout(pdf_path, timeout=60)
    if err: return jsonify({"ok": False, "error": f"PDF download error: {err}\n文件正在从 OneDrive 下载中，请稍后重试。"}), 504
    if not pdf_bytes: return jsonify({"ok": False, "error": "PDF is empty"}), 500
    with _predownload_lock: _predownloaded.add(edc_no); _predownloading.discard(edc_no)
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            words = pdf.pages[0].extract_words()
    except Exception as e:
        return jsonify({"ok": False, "error": f"PDF parse error: {e}"}), 500
    if not text.strip(): return jsonify({"ok": False, "error": "PDF has no extractable text"}), 400

    def find(pattern, default=""):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else default

    report_no = find(r"N\.\s*(\d{6,12})"); report_date = find(r"Date:\s*(\d{2}\.\d{2}\.\d{4})")
    supplier_code = find(r"Supplier Code\.:\s*(\S+)"); drawing = find(r"Drawing:\s*(\S+)")
    description = ""
    for w in words:
        if w["text"] == "Description:":
            y = w["top"]
            line = sorted([ww for ww in words if abs(ww["top"] - y) < 5 and ww["x0"] < 290 and ww["text"] != "Description:"], key=lambda x: x["x0"])
            description = " ".join(ww["text"] for ww in line); break
    m_sup = re.search(r"Rif\.:\s*(.+)", text)
    supplier_name = re.sub(r"\s+\d+.*$", "", m_sup.group(1)).strip() if m_sup else ""
    received = find(r"Received Parts\.:\s*(\d+)"); rejected = find(r"Rejected Parts:\s*(\d+)"); lot_number = find(r"Lot\s*check[.:]?\s*(\S+)")
    m_rem = re.search(r"\*{5,}\s*\n(.+?)(?=SUPPLY QUALITY|SAMPLE LAB|PIAGGIO & C\.|$)", text, re.DOTALL)
    removals = m_rem.group(1).strip() if m_rem else ""
    if not removals:
        blocks = re.findall(r"REMOVALS\s*\n(.*?)(?=REMOVALS|SUPPLY QUALITY|\Z)", text, re.DOTALL | re.IGNORECASE)
        if blocks:
            # 优先选英文块（检测常见英文关键词）
            def _is_english(t):
                en = sum(1 for w in ['parts', 'rejected', 'compliant', 'found', 'defect', 'check'] if w in t.lower())
                it = sum(1 for w in ['conformi', 'pezzi', 'imballo', 'verifiche', 'consegna', 'riscontrato'] if
                         w in t.lower())
                return en > it

            eng_blocks = [b.strip() for b in blocks if _is_english(b)]
            removals = eng_blocks[0] if eng_blocks else blocks[0].strip()
        else:
            removals = ""
    issue_lines = [removals] if removals else []
    try:
        if int(rejected) > 0: issue_lines.append(f"\nRejected: {rejected} / Received: {received} pcs  |  Report Date: {report_date}")
    except (ValueError, TypeError): pass

    return jsonify({"ok": True, "pdf_name": pdf_path.name, "pdf_path": str(pdf_path), "fields": {
        "tr_no": f"TR-EDC-{report_no or edc_no}", "report_no": report_no or edc_no,
        "report_date": report_date, "supplier_code": supplier_code, "supplier_name": supplier_name,
        "part_number": drawing, "part_name": description,
        "issue_description": "\n".join(issue_lines),
        "received_parts": received, "rejected_parts": rejected, "eight_d_status": "NOT_RECEIVED",
        "lot_number": lot_number,
    }})

@tr_bp.route("/<int:tr_id>/regenerate-summary", methods=["POST"])
def regenerate_summary(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    threading.Thread(
        target=_generate_issue_summary,
        args=(current_app._get_current_object(), tr.id),
        daemon=True
    ).start()
    flash("✅ AI 正在重新生成问题摘要，稍后刷新查看", "success")
    return redirect(url_for("tr.edit_tr", tr_id=tr_id))

@tr_bp.route("/ai-status/<int:tr_id>")
def ai_status(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    return jsonify({
        "done": bool(tr.issue_summary),
        "summary": tr.issue_summary or "",
    })

@tr_bp.route("/8d-detail/<int:tr_id>")
def eight_d_detail(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    has_8d_doc = TRDocument.query.filter_by(
        tr_id=tr.id, doc_type="8d_report"
    ).first() is not None
    return jsonify({
        "tr_no": tr.tr_no,
        "status": tr.eight_d_status or "NOT_REQUIRED",
        "root_cause": tr.eight_d_root_cause or "",
        "root_cause_en": tr.eight_d_root_cause_en or "",
        "escape_cause": tr.eight_d_escape_cause or "",
        "escape_cause_en": tr.eight_d_escape_cause_en or "",
        "action": tr.eight_d_action or "",
        "action_en": tr.eight_d_action_en or "",
        "has_8d_doc": has_8d_doc,
        "part_number": tr.part_number or "",
        "part_name": tr.part_name or "",
        "escape_action": tr.eight_d_escape_action or "",
        "escape_action_en": tr.eight_d_escape_action_en or "",
    })

def _extract_8d_for_tr(app, tr_id):
    """找到该 TR 的 8D 报告附件，AI 提取根因和措施"""
    import os
    from ...ai_helper import extract_8d
    with app.app_context():
        try:
            tr = TroubleReport.query.get(tr_id)
            if not tr:
                return
            doc = TRDocument.query.filter_by(
                tr_id=tr.id, doc_type="8d_report"
            ).order_by(TRDocument.created_at.desc()).first()
            if not doc:
                return
            file_path = os.path.join(app.config["UPLOAD_DIR"], doc.rel_path)
            if not os.path.exists(file_path):
                return
            result = extract_8d(file_path, logger=app.logger)
            if result:
                tr.eight_d_root_cause = result.get("root_cause", "")
                tr.eight_d_root_cause_en = result.get("root_cause_en", "")
                tr.eight_d_escape_cause = result.get("escape_cause", "")
                tr.eight_d_escape_cause_en = result.get("escape_cause_en", "")
                tr.eight_d_action = result.get("action", "")
                tr.eight_d_action_en = result.get("action_en", "")
                tr.eight_d_escape_action = result.get("escape_action", "")
                tr.eight_d_escape_action_en = result.get("escape_action_en", "")
                db.session.commit()
                app.logger.info(
                    f"[AI 8D] TR {tr.tr_no} saved | "
                    f"occ_cn={len(tr.eight_d_root_cause)} occ_en={len(tr.eight_d_root_cause_en)} "
                    f"esc_cn={len(tr.eight_d_escape_cause)} esc_en={len(tr.eight_d_escape_cause_en)}"
                )
        except Exception as e:
            app.logger.warning(f"[AI 8D] failed for TR {tr_id}: {e}")

@tr_bp.route("/8d-extract/<int:tr_id>", methods=["POST"])
def eight_d_extract_ajax(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    doc = TRDocument.query.filter_by(tr_id=tr.id, doc_type="8d_report").first()
    if not doc:
        return jsonify({"ok": False, "msg": "该 TR 没有 8D 报告附件"})
    threading.Thread(
        target=_extract_8d_for_tr,
        args=(current_app._get_current_object(), tr.id),
        daemon=True
    ).start()
    return jsonify({"ok": True, "msg": "AI 正在分析，约 20-40 秒后刷新查看"})

@tr_bp.route("/<int:tr_id>/toggle-pin", methods=["POST"])
def toggle_pin(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    tr.is_pinned = not tr.is_pinned
    db.session.commit()
    return jsonify({"ok": True, "pinned": tr.is_pinned})

@tr_bp.route("/<int:tr_id>/investigation", methods=["POST"])
def save_investigation(tr_id):
    tr = TroubleReport.query.get_or_404(tr_id)
    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "").strip()
    tr.investigation_note = note or None
    db.session.commit()
    return jsonify({"ok": True, "note": tr.investigation_note or ""})