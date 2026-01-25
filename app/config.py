import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    # 基础目录
    BASE_DIR = os.getenv(
        "BASE_DIR",
        r"D:\supplier_portal_data"
    )

    # 数据库配置
    DB_DIR = os.path.join(BASE_DIR, "db")
    DB_PATH = os.path.join(DB_DIR, "app.sqlite3")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 上传文件配置（与 db 平级，不是子目录）
    UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

    # 最大上传文件大小：50MB
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024