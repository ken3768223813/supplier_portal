import tempfile
import unittest

from app import create_app
from app.extensions import db
from app.models import DrillPhrase, DrillProgress


class DrillRouteTests(unittest.TestCase):
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
        cls.phrase = DrillPhrase(
            category="quality",
            difficulty="intermediate",
            context_cn="供应商会议",
            cn="请隔离所有受影响库存。",
            en="Please isolate all affected stock.",
            status="approved",
            active=True,
        )
        db.session.add(cls.phrase)
        db.session.commit()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.context.pop()
        cls.temp_dir.cleanup()

    def test_lab_pages_render(self):
        for path in ("/drill/", "/drill/scenarios", "/drill/materials"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"SQE English Lab", response.data)

    def test_rating_creates_server_side_progress(self):
        response = self.client.post(
            "/drill/api/rate",
            json={
                "phrase_id": self.phrase.id,
                "mode": "quick",
                "rating": "good",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        progress = DrillProgress.query.filter_by(phrase_id=self.phrase.id).one()
        self.assertEqual(progress.attempts, 1)
        self.assertEqual(progress.successes, 1)
        self.assertEqual(progress.last_mode, "quick")
        self.assertEqual(progress.interval_days, 2)


if __name__ == "__main__":
    unittest.main()
