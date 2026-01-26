import os
from flask import Flask
from flask_migrate import Migrate  # ✅ 添加这一行
from .config import Config
from .extensions import db
from . import models  # ✅ 确保所有模型（含TR）被加载


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    # 确保 instance 文件夹存在（但不再用于上传文件）
    os.makedirs(app.instance_path, exist_ok=True)

    # ✅ 使用 config.py 中配置的目录
    os.makedirs(app.config["DB_DIR"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    # init extensions
    db.init_app(app)
    migrate = Migrate(app, db)  # ✅ 添加这一行，初始化 Flask-Migrate

    # 注册蓝图
    from .blueprints.main import main_bp
    app.register_blueprint(main_bp)

    from .blueprints.suppliers import suppliers_bp
    app.register_blueprint(suppliers_bp, url_prefix="/suppliers")

    from .blueprints.supplier_ws import supplier_ws_bp
    app.register_blueprint(supplier_ws_bp)

    from .blueprints.parts import parts_bp
    app.register_blueprint(parts_bp)

    from .blueprints.docs import docs_bp
    app.register_blueprint(docs_bp)

    from .blueprints.tr import tr_bp
    app.register_blueprint(tr_bp, url_prefix="/tr")

    from app.blueprints.Trip import trip_bp
    app.register_blueprint(trip_bp, url_prefix='/trip')

    # 在其他 blueprint 导入后添加
    from app.blueprints.knowledge import knowledge_bp
    app.register_blueprint(knowledge_bp, url_prefix='/knowledge')

    # 在其他 blueprint 后添加
    from app.blueprints.file import file_bp
    app.register_blueprint(file_bp, url_prefix='/file')

    # CLI：初始化数据库 + 导入种子数据
    from .seed import seed_suppliers

    @app.cli.command("init-db")
    def init_db():
        """Create tables and seed initial suppliers."""
        with app.app_context():
            db.create_all()
            seed_suppliers()
            print("✅ DB initialized and suppliers seeded.")

    # 调试信息
    print("=" * 60)
    print("✅ SQLALCHEMY_DATABASE_URI =", app.config["SQLALCHEMY_DATABASE_URI"])
    print("✅ DB file exists =", os.path.exists(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")))
    print("✅ UPLOAD_DIR =", app.config["UPLOAD_DIR"])
    print("=" * 60)

    return app