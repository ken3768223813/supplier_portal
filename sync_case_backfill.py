import argparse

from app import create_app
from app.extensions import db
from app.models import TroubleReport, TRDocument
from app.blueprints.tr.routes import (
    CASE_SYNC_FIELDS,
    CASE_JOIN_DOC_TYPES,
    _case_source_tr,
    _copy_case_document_to_tr,
    _copy_case_fields,
    _has_case_value,
)


def iter_case_numbers(case_no=None):
    query = db.session.query(TroubleReport.case_no).filter(
        TroubleReport.case_no.isnot(None),
        TroubleReport.case_no != "",
    )
    if case_no:
        query = query.filter(TroubleReport.case_no == case_no)
    return [row[0] for row in query.distinct().order_by(TroubleReport.case_no).all()]


def sync_case(app, case_no, dry_run=False):
    source = _case_source_tr(case_no)
    if not source:
        return {"case_no": case_no, "source": None, "trs": 0, "fields": 0, "docs": 0}

    targets = (
        TroubleReport.query
        .filter(TroubleReport.case_no == case_no, TroubleReport.id != source.id)
        .all()
    )
    source_docs = (
        TRDocument.query
        .filter(TRDocument.tr_id == source.id, TRDocument.doc_type.in_(CASE_JOIN_DOC_TYPES))
        .order_by(TRDocument.created_at.desc())
        .all()
    )

    changed_trs = 0
    copied_fields = 0
    copied_docs = 0
    for target in targets:
        if dry_run:
            field_count = sum(
                1
                for field in CASE_SYNC_FIELDS
                if _has_case_value(getattr(source, field))
            )
        else:
            field_count = _copy_case_fields(source, target)
        doc_count = 0
        for doc in source_docs:
            if dry_run:
                with db.session.no_autoflush:
                    exists = TRDocument.query.filter_by(
                        tr_id=target.id,
                        original_name=doc.original_name,
                        doc_type=doc.doc_type,
                    ).first()
                if not exists:
                    doc_count += 1
            elif _copy_case_document_to_tr(app, source, doc, target):
                doc_count += 1

        if field_count or doc_count:
            changed_trs += 1
            copied_fields += field_count
            copied_docs += doc_count

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return {
        "case_no": case_no,
        "source": source.tr_no,
        "trs": changed_trs,
        "fields": copied_fields,
        "docs": copied_docs,
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill shared Case data into existing TRs.")
    parser.add_argument("--case-no", help="Only sync one case, for example CASE-2026-001")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        total_trs = total_fields = total_docs = 0
        for case_no in iter_case_numbers(args.case_no):
            result = sync_case(app, case_no, dry_run=args.dry_run)
            if not result["source"]:
                continue
            total_trs += result["trs"]
            total_fields += result["fields"]
            total_docs += result["docs"]
            print(
                f"{result['case_no']}: source={result['source']} "
                f"trs={result['trs']} fields={result['fields']} docs={result['docs']}"
            )
        mode = "DRY RUN" if args.dry_run else "DONE"
        print(f"{mode}: trs={total_trs} fields={total_fields} docs={total_docs}")


if __name__ == "__main__":
    main()
