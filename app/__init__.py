import os
from flask import Flask
from .config import Config
from .extensions import db

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    # 确保 instance 文件夹存在（用于放 sqlite）
    os.makedirs(app.instance_path, exist_ok=True)

    # init extensions
    db.init_app(app)

    # 注册蓝图
    from .blueprints.main import main_bp
    app.register_blueprint(main_bp)

    from .blueprints.suppliers import suppliers_bp
    app.register_blueprint(suppliers_bp, url_prefix="/suppliers")

    # CLI：初始化数据库 + 导入种子数据
    from .seed import seed_suppliers
    @app.cli.command("init-db")
    def init_db():
        """Create tables and seed initial suppliers."""
        with app.app_context():
            db.create_all()
            seed_suppliers()
            print("✅ DB initialized and suppliers seeded.")

    return app
