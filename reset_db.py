import os
from app import create_app, db
from app.seed import seed_suppliers

# 创建应用
app = create_app()

with app.app_context():
    print("=" * 50)
    print("🗑️  删除所有旧表...")
    db.drop_all()

    print("📦 根据模型创建所有表...")
    db.create_all()

    print("🌱 导入种子数据...")
    try:
        seed_suppliers()
        print("✅ 种子数据导入成功")
    except Exception as e:
        print(f"⚠️  种子数据导入失败: {e}")

    print("=" * 50)
    print("✅ 数据库初始化完成！")
    print(f"📍 数据库位置: {app.config['SQLALCHEMY_DATABASE_URI']}")