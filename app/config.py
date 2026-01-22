import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    # 未来用于供应商资料上传（先预留）
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads"))
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DB_PATH = os.path.join(BASE_DIR, "..", "instance", "supplier_portal.sqlite")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.abspath(DB_PATH)
    SQLALCHEMY_TRACK_MODIFICATIONS = False