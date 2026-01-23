import pandas as pd

from app import create_app
from app.extensions import db
from app.models import Supplier


EXCEL_PATH = "suppliers.xlsx"  # Excel 路径


def import_suppliers():
    df = pd.read_excel(EXCEL_PATH)

    app = create_app()
    with app.app_context():
        for _, row in df.iterrows():
            code = str(row["code"]).strip()

            if not code:
                continue

            supplier = Supplier.query.filter_by(code=code).first()

            if not supplier:
                supplier = Supplier(code=code)
                db.session.add(supplier)

            supplier.name = row.get("name")
            supplier.chinese_name = row.get("chinese_name")

            # is_active 处理
            val = row.get("is_active", 1)
            supplier.is_active = bool(val)

        db.session.commit()
        print("✅ Suppliers imported successfully.")


if __name__ == "__main__":
    import_suppliers()
