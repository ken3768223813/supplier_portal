import os
import tempfile
import unittest
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import TRDocument, TroubleReport


class TRDocumentRevealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "DB_DIR": cls.temp_dir.name,
                "UPLOAD_DIR": cls.temp_dir.name,
            }
        )
        cls.context = cls.app.app_context()
        cls.context.push()
        db.create_all()

        cls.tr = TroubleReport(
            tr_no="TR-TEST-REVEAL",
            supplier_code="SUP-TEST",
            supplier_name="Test Supplier",
            issue_description="Test issue",
            case_no="CASE-TEST-001",
            status="Closed",
            eight_d_status="RECEIVED_PASS",
            eight_d_root_cause="Verified root cause",
            eight_d_action="Verified corrective action",
        )
        db.session.add(cls.tr)
        db.session.flush()

        cls.target_tr = TroubleReport(
            tr_no="TR-TEST-PENDING",
            supplier_code="SUP-TEST",
            supplier_name="Test Supplier",
            issue_description="Same case issue",
            case_no="CASE-TEST-001",
            status="Open",
            eight_d_status="NOT_RECEIVED",
        )
        db.session.add(cls.target_tr)
        db.session.flush()

        cls.office_rel_path = os.path.join("tr", "report.xlsx")
        cls.pdf_rel_path = os.path.join("tr", "report.pdf")
        os.makedirs(os.path.join(cls.temp_dir.name, "tr"), exist_ok=True)
        for rel_path in (cls.office_rel_path, cls.pdf_rel_path):
            with open(os.path.join(cls.temp_dir.name, rel_path), "wb") as file:
                file.write(b"test")

        cls.office_doc = TRDocument(
            tr_id=cls.tr.id,
            doc_type="8d_report",
            title="Excel 8D",
            original_name="report.xlsx",
            stored_name="report.xlsx",
            rel_path=cls.office_rel_path,
            size=4,
        )
        cls.pdf_doc = TRDocument(
            tr_id=cls.tr.id,
            doc_type="quality_report",
            title="PDF report",
            original_name="report.pdf",
            stored_name="report.pdf",
            rel_path=cls.pdf_rel_path,
            size=4,
        )
        db.session.add_all([cls.office_doc, cls.pdf_doc])
        db.session.commit()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.context.pop()
        cls.temp_dir.cleanup()

    @patch("app.blueprints.tr.routes._reveal_file_in_manager")
    def test_non_pdf_is_revealed_in_file_manager(self, reveal):
        response = self.client.post(
            f"/tr/{self.tr.id}/documents/{self.office_doc.id}/reveal"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        reveal.assert_called_once_with(
            os.path.abspath(os.path.join(self.temp_dir.name, self.office_rel_path))
        )

    @patch("app.blueprints.tr.routes._reveal_file_in_manager")
    def test_pdf_keeps_browser_preview(self, reveal):
        response = self.client.post(
            f"/tr/{self.tr.id}/documents/{self.pdf_doc.id}/reveal"
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])
        reveal.assert_not_called()

    def test_document_panel_uses_reveal_only_for_non_pdf(self):
        response = self.client.get(f"/tr/{self.tr.id}/documents/panel")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f"/tr/{self.tr.id}/documents/{self.office_doc.id}/reveal", html
        )
        self.assertIn(
            f"/tr/{self.tr.id}/documents/{self.pdf_doc.id}/view", html
        )
        self.assertNotIn(
            f"/tr/{self.tr.id}/documents/{self.pdf_doc.id}/reveal", html
        )

    def test_case_detail_shows_clickable_document_count(self):
        response = self.client.get("/tr/cases/CASE-TEST-001")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        for column in (
            "Part No.", "Part Name", "Issue", "8D", "Status", "Debit", "Doc", "Action"
        ):
            self.assertIn(f">{column}</th>", html)
        self.assertIn(f"openCaseTRDocuments({self.tr.id})", html)
        self.assertIn(f"openRcca({self.tr.id})", html)
        self.assertIn(f"toggleCasePin({self.tr.id}", html)
        self.assertIn(">\n                2\n              </button>", html)
        self.assertIn("Case 状态待统一", html)
        self.assertIn("同步结案结果", html)
        self.assertIn(self.tr.tr_no, html)
        self.assertIn(self.target_tr.tr_no, html)

    def test_case_resolution_sync_closes_sibling_and_copies_only_8d_documents(self):
        response = self.client.post("/tr/cases/CASE-TEST-001/sync-resolution")

        self.assertEqual(response.status_code, 302)
        db.session.expire_all()
        target = db.session.get(TroubleReport, self.target_tr.id)
        self.assertEqual(target.status, "Closed")
        self.assertEqual(target.eight_d_status, "RECEIVED_PASS")
        self.assertEqual(target.eight_d_root_cause, "Verified root cause")
        self.assertEqual(target.eight_d_action, "Verified corrective action")

        copied_documents = TRDocument.query.filter_by(tr_id=target.id).all()
        self.assertEqual(len(copied_documents), 1)
        self.assertEqual(copied_documents[0].doc_type, "8d_report")
        self.assertEqual(copied_documents[0].original_name, "report.xlsx")


if __name__ == "__main__":
    unittest.main()
