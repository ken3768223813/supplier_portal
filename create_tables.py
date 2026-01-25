from app import create_app
from app.extensions import db

if __name__ == '__main__':
    app = create_app()

    with app.app_context():
        # 创建所有表
        db.create_all()

        # 验证表是否创建
        from sqlalchemy import inspect

        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        print("\n" + "=" * 60)
        print("📋 现有数据表:")
        for table in sorted(tables):
            print(f"  ✓ {table}")

        if 'tr_documents' in tables:
            print("\n✅ tr_documents 表创建成功!")
        else:
            print("\n❌ tr_documents 表未创建")
        print("=" * 60 + "\n")