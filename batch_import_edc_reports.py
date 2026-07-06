#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch import main EDC report PDFs into existing TR-EDC documents.

Examples:
  python batch_import_edc_reports.py --dry-run
  python batch_import_edc_reports.py
  python batch_import_edc_reports.py --limit 20
  python batch_import_edc_reports.py --edc-no 123456789
  python batch_import_edc_reports.py --force
"""

import argparse
import os
import re
import threading
import uuid
from pathlib import Path

from werkzeug.utils import secure_filename

from app import create_app
from app.extensions import db
from app.models import TroubleReport, TRDocument


PDF_MIME = "application/pdf"
EDC_REPORT_REMARK = "Auto-imported EDC report PDF"


def read_file_with_timeout(file_path, timeout=60):
    holder = {"data": None, "error": None}
    done = threading.Event()

    def _read():
        try:
            with open(str(file_path), "rb") as f:
                holder["data"] = f.read()
        except Exception as exc:
            holder["error"] = str(exc)
        finally:
            done.set()

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    if not done.wait(timeout=timeout):
        return None, f"Download timeout (>{timeout}s)"
    return holder["data"], holder["error"]


def is_cloud_placeholder(file_path):
    try:
        st = os.stat(str(file_path))
        return bool(getattr(st, "st_file_attributes", 0) & 0x00400000)
    except Exception:
        return False


def extract_edc_no(tr_no):
    m = re.match(r"TR-EDC-(\d+)$", tr_no or "")
    return m.group(1) if m else None


def find_edc_report_pdfs(root, edc_no):
    pdfs = []
    for p in root.rglob(f"*{edc_no}*.pdf"):
        if p.is_file():
            pdfs.append(p.resolve())

    def sort_key(path):
        stem = path.stem.lower()
        exact = 0 if stem == edc_no.lower() else 1
        starts = 0 if stem.startswith(edc_no.lower()) else 1
        return exact, starts, len(stem), path.name.lower()

    return sorted(dict.fromkeys(pdfs), key=sort_key)


def existing_original_names(tr):
    return {doc.original_name for doc in tr.documents}


def import_pdf_for_tr(app, tr, pdf_path, edc_no, dry_run=False, force=False):
    if not force and pdf_path.name in existing_original_names(tr):
        return "skipped", "already imported"

    title = f"EDC Report {edc_no}"
    if dry_run:
        return "would_import", str(pdf_path)

    timeout = 60 if is_cloud_placeholder(pdf_path) else 20
    data, err = read_file_with_timeout(pdf_path, timeout=timeout)
    if err:
        return "failed", err
    if not data:
        return "failed", "empty PDF"

    tr_dir = os.path.join("tr_docs", secure_filename(tr.tr_no))
    full_dir = os.path.join(app.config["UPLOAD_DIR"], tr_dir)
    os.makedirs(full_dir, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}.pdf"
    file_path = os.path.join(full_dir, stored_name)
    with open(file_path, "wb") as f:
        f.write(data)

    db.session.add(TRDocument(
        tr_id=tr.id,
        doc_type="quality_report",
        title=title,
        original_name=pdf_path.name,
        stored_name=stored_name,
        rel_path=os.path.join(tr_dir, stored_name),
        mime=PDF_MIME,
        size=len(data),
        remark=EDC_REPORT_REMARK,
    ))
    return "imported", str(pdf_path)


def iter_target_trs(edc_no=None, limit=None):
    query = TroubleReport.query.filter(TroubleReport.tr_no.like("TR-EDC-%"))
    if edc_no:
        query = query.filter(TroubleReport.tr_no == f"TR-EDC-{edc_no}")
    query = query.order_by(TroubleReport.created_at.desc(), TroubleReport.id.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


def main():
    parser = argparse.ArgumentParser(
        description="Batch import main EDC report PDFs for existing TR-EDC records."
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print what would be imported.")
    parser.add_argument("--force", action="store_true", help="Import even if the same original filename already exists.")
    parser.add_argument("--limit", type=int, help="Process at most N TR records.")
    parser.add_argument("--edc-no", help="Only process one EDC number, e.g. 123456789.")
    parser.add_argument("--root", help="Override EDC OneDrive root path.")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        root_value = args.root or app.config.get("EDC_ONEDRIVE_PATH")
        if not root_value:
            raise SystemExit("EDC_ONEDRIVE_PATH is not configured.")

        root = Path(root_value)
        if not root.exists():
            raise SystemExit(f"EDC root path does not exist: {root}")

        trs = iter_target_trs(edc_no=args.edc_no, limit=args.limit)
        if not trs:
            print("No TR-EDC records found.")
            return

        stats = {
            "trs": len(trs),
            "imported": 0,
            "would_import": 0,
            "skipped": 0,
            "missing": 0,
            "failed": 0,
        }

        for tr in trs:
            edc_no = extract_edc_no(tr.tr_no)
            if not edc_no:
                stats["skipped"] += 1
                print(f"[SKIP] {tr.tr_no}: invalid TR-EDC number")
                continue

            pdfs = find_edc_report_pdfs(root, edc_no)
            if not pdfs:
                stats["missing"] += 1
                print(f"[MISS] {tr.tr_no}: no PDF found for EDC {edc_no}")
                continue

            for pdf_path in pdfs:
                status, detail = import_pdf_for_tr(
                    app=app,
                    tr=tr,
                    pdf_path=pdf_path,
                    edc_no=edc_no,
                    dry_run=args.dry_run,
                    force=args.force,
                )
                stats[status] = stats.get(status, 0) + 1
                print(f"[{status.upper()}] {tr.tr_no}: {pdf_path.name} | {detail}")

        if args.dry_run:
            db.session.rollback()
        else:
            db.session.commit()

        print(
            "Done. "
            f"TRs={stats['trs']}, imported={stats['imported']}, "
            f"would_import={stats['would_import']}, skipped={stats['skipped']}, "
            f"missing={stats['missing']}, failed={stats['failed']}"
        )


if __name__ == "__main__":
    main()
