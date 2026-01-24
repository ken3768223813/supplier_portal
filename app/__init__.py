import os
from flask import Flask
from .config import Config
from .extensions import db
from . import models  # ✅ 确保所有模型（含TR）被加载


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    # 确保 instance 文件夹存在（用于放 sqlite）
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["UPLOAD_DIR"] = os.path.join(app.instance_path, "uploads")

    # ✅ 确保上传目录存在（instance/uploads）
    os.makedirs(os.path.join(app.instance_path, "uploads"), exist_ok=True)

    os.makedirs(app.config["DB_DIR"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    # init extensions
    db.init_app(app)

    # 注册蓝图
    from .blueprints.main import main_bp
    app.register_blueprint(main_bp)

    from .blueprints.suppliers import suppliers_bp
    app.register_blueprint(suppliers_bp, url_prefix="/suppliers")

    # ✅ 新增：供应商工作台 / 零部件 / 文档
    from .blueprints.supplier_ws import supplier_ws_bp
    app.register_blueprint(supplier_ws_bp)  # 它自己带 url_prefix="/suppliers"

    from .blueprints.parts import parts_bp
    app.register_blueprint(parts_bp)        # prefix: /suppliers/<code>/parts

    from .blueprints.docs import docs_bp
    app.register_blueprint(docs_bp)         # prefix: /suppliers/<code>/docs

    from .blueprints.tr import tr_bp
    app.register_blueprint(tr_bp, url_prefix="/tr")

    # CLI：初始化数据库 + 导入种子数据
    from .seed import seed_suppliers

    @app.cli.command("init-db")
    def init_db():
        """Create tables and seed initial suppliers."""
        with app.app_context():
            db.create_all()
            seed_suppliers()
            print("✅ DB initialized and suppliers seeded.")

    print("✅ SQLALCHEMY_DATABASE_URI =", app.config["SQLALCHEMY_DATABASE_URI"])
    print("✅ DB file exists =", os.path.exists(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")))

    return app


