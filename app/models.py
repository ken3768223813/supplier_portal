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

