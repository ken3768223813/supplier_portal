from datetime import datetime
from .extensions import db

class Supplier(db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, index=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    china_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parts = db.relationship("Part", backref="supplier", lazy=True, cascade="all, delete-orphan")
    documents = db.relationship("Document", backref="supplier", lazy=True, cascade="all, delete-orphan")


class Part(db.Model):
    __tablename__ = "parts"
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)

    pn = db.Column(db.String(128), nullable=False)          # part number
    description = db.Column(db.String(255))
    project = db.Column(db.String(128))
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    documents = db.relationship("Document", backref="part", lazy=True, cascade="all, delete-orphan")


class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey("parts.id"), nullable=True)

    # drawing / control_plan / spec / ppap / audit / 8d ...
    doc_type = db.Column(db.String(50), nullable=False)

    title = db.Column(db.String(255), nullable=False)
    revision = db.Column(db.String(50))      # A, B, C / 01 / Rev.2 ...
    status = db.Column(db.String(30), default="valid")  # valid/draft/obsolete
    file_path = db.Column(db.String(500), nullable=False)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Drawing(db.Model):
    __tablename__ = "drawings"
    id = db.Column(db.Integer, primary_key=True)

    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    part_id = db.Column(db.Integer, db.ForeignKey("parts.id"), nullable=False, index=True)

    # 版本信息
    revision = db.Column(db.String(50), nullable=False, default="A0")   # 例：A0 / A1 / Rev.02
    title = db.Column(db.String(255))                                  # 可选：图纸名称
    remark = db.Column(db.Text)                                        # 备注
    effective_date = db.Column(db.Date)                                # 生效日期/批准日期（可选）

    # 文件信息
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)            # 实际保存文件名
    rel_path = db.Column(db.String(500), nullable=False)               # 相对 uploads 的路径
    mime = db.Column(db.String(100))
    size = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    part = db.relationship("Part", backref=db.backref("drawings", lazy="dynamic", cascade="all, delete-orphan"))



from sqlalchemy import CheckConstraint

class TroubleReport(db.Model):
    __tablename__ = "trouble_reports"

    id = db.Column(db.Integer, primary_key=True)

    tr_no = db.Column(db.String(50), nullable=False, unique=True, index=True)
    supplier_code = db.Column(db.String(50), nullable=False, index=True)
    supplier_name = db.Column(db.String(255), nullable=False)

    part_number = db.Column(db.String(100), nullable=True, index=True)
    part_name = db.Column(db.String(255), nullable=True)

    issue_description = db.Column(db.Text, nullable=False)

    severity = db.Column(db.String(20), nullable=True, index=True)

    # 旧字段保留：可以继续存“8D编号/链接/备注”
    eight_d = db.Column(db.String(50), nullable=True, index=True)

    # ✅ 新增：8D 状态枚举（用于灯号/筛选）
    eight_d_status = db.Column(db.String(30), nullable=False, default="NOT_REQUIRED", index=True)

    status = db.Column(db.String(30), nullable=False, default="Open", index=True)
    remark = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "eight_d_status IN ('NOT_REQUIRED','NOT_RECEIVED','RECEIVED_REJECT','RECEIVED_PASS')",
            name="ck_tr_8d_status"
        ),
    )

    def __repr__(self):
        return f"<TR {self.tr_no}>"



