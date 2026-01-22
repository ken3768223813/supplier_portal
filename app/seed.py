from .extensions import db
from .models import Supplier

DEFAULT_SUPPLIERS = [
    ("ZSU0026419", "NOCO"),
    ("ITMD10793", "Supplier ITMD10793"),
    ("ITV0014680", "Supplier ITV0014680"),
    # 你可以继续加……
]

def seed_suppliers():
    """Insert suppliers if not exist (idempotent)."""
    for code, name in DEFAULT_SUPPLIERS:
        exists = Supplier.query.filter_by(code=code).first()
        if not exists:
            db.session.add(Supplier(code=code, name=name))
    db.session.commit()
