import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    DB_DIR = os.getenv(
        "DB_DIR",
        r"D:\supplier_portal_data\db"   # ← D 盘
    )

    DB_PATH = os.path.join(DB_DIR, "app.sqlite3")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_DIR = os.path.join(DB_DIR, "uploads")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
