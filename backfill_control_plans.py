"""Extract structured drafts for existing control-plan attachments."""
import argparse
import json
import os

from app import create_app
from app.control_plan_helper import PARSER_VERSION, extract_control_plan, sha256_file
from app.extensions import db
from app.models import ControlPlan, ControlPlanVersion


def backfill(force=False, force_ai=False, only_id=None):
    app = create_app()
    with app.app_context():
        query = ControlPlan.query.order_by(ControlPlan.id)
        if only_id:
            query = query.filter(ControlPlan.id == only_id)

        processed = 0
        for cp in query.all():
            versions = cp.versions.order_by(ControlPlanVersion.version_no).all()
            if not versions and cp.rel_path:
                file_path = os.path.join(
                    app.config["UPLOAD_DIR"], cp.rel_path.replace("/", os.sep)
                )
                if os.path.exists(file_path):
                    version = ControlPlanVersion(
                        cp_id=cp.id,
                        version_no=1,
                        revision=cp.revision,
                        status="review",
                        extract_status="pending",
                        original_name=cp.original_name or os.path.basename(file_path),
                        stored_name=cp.stored_name or os.path.basename(file_path),
                        rel_path=cp.rel_path,
                        mime=cp.mime,
                        size=cp.size or os.path.getsize(file_path),
                        file_sha256=sha256_file(file_path),
                    )
                    db.session.add(version)
                    db.session.flush()
                    versions = [version]

            for version in versions:
                if not force and version.extract_status not in {"pending", "failed"}:
                    continue
                file_path = os.path.join(
                    app.config["UPLOAD_DIR"], version.rel_path.replace("/", os.sep)
                )
                if not os.path.exists(file_path):
                    version.extract_status = "failed"
                    version.extraction_error = "Source file not found"
                    cp.structure_status = "failed"
                    db.session.commit()
                    print(f"[missing] {cp.cp_no} V{version.version_no}: {file_path}")
                    continue
                try:
                    data = extract_control_plan(
                        file_path, force_ai=force_ai, logger=app.logger
                    )
                    version.structured_json = json.dumps(data, ensure_ascii=False)
                    version.metadata_json = json.dumps(
                        data.get("metadata", {}), ensure_ascii=False
                    )
                    version.quality_issues = json.dumps(
                        data.get("quality_issues", []), ensure_ascii=False
                    )
                    version.source_sheet = data.get("source_sheet")
                    version.source_template = data.get("source_template")
                    version.parser_version = data.get("parser_version") or PARSER_VERSION
                    version.ai_model = data.get("ai_model")
                    version.confidence = data.get("confidence")
                    version.quality_score = data.get("quality_score")
                    version.file_sha256 = version.file_sha256 or sha256_file(file_path)
                    version.extract_status = "review"
                    version.status = "review"
                    version.extraction_error = None
                    cp.structure_status = "review"
                    cp.quality_score = version.quality_score
                    cp.source_template = version.source_template
                    db.session.commit()
                    processed += 1
                    char_count = sum(
                        len(step.get("characteristics", []))
                        for step in data.get("steps", [])
                    )
                    print(
                        f"[ok] {cp.cp_no} V{version.version_no}: "
                        f"{len(data.get('steps', []))} processes, "
                        f"{char_count} characteristics"
                    )
                except Exception as exc:
                    db.session.rollback()
                    version = db.session.get(ControlPlanVersion, version.id)
                    cp = db.session.get(ControlPlan, cp.id)
                    version.extract_status = "failed"
                    version.extraction_error = str(exc)
                    cp.structure_status = "failed"
                    db.session.commit()
                    print(f"[failed] {cp.cp_no} V{version.version_no}: {exc}")
        print(f"Completed: {processed} version(s) extracted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--force-ai", action="store_true")
    parser.add_argument("--only-id", type=int)
    args = parser.parse_args()
    backfill(force=args.force, force_ai=args.force_ai, only_id=args.only_id)
