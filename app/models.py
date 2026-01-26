from datetime import datetime
from .extensions import db

class Supplier(db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, index=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    chinese_name = db.Column(db.String(255))
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

    documents = db.relationship("TRDocument", backref="trouble_report", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "eight_d_status IN ('NOT_REQUIRED','NOT_RECEIVED','RECEIVED_REJECT','RECEIVED_PASS')",
            name="ck_tr_8d_status"
        ),
    )

    def __repr__(self):
        return f"<TR {self.tr_no}>"


class TRDocument(db.Model):
    __tablename__ = "tr_documents"

    id = db.Column(db.Integer, primary_key=True)
    tr_id = db.Column(db.Integer, db.ForeignKey("trouble_reports.id"), nullable=False, index=True)

    # 文档类型
    doc_type = db.Column(db.String(50), nullable=False, index=True)
    # 可选值: quality_report, test_report, 8d_report, photo, other

    # 文档标题
    title = db.Column(db.String(255), nullable=False)

    # 文件信息
    original_name = db.Column(db.String(255), nullable=False)  # 原始文件名
    stored_name = db.Column(db.String(255), nullable=False)  # 存储文件名（UUID）
    rel_path = db.Column(db.String(500), nullable=False)  # 相对路径
    mime = db.Column(db.String(100))  # MIME 类型
    size = db.Column(db.Integer)  # 文件大小（字节）

    # 备注
    remark = db.Column(db.Text)

    # 创建时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<TRDocument {self.title} for TR#{self.tr_id}>"



class BusinessTrip(db.Model):
    """出差记录表"""
    __tablename__ = 'business_trips'

    id = db.Column(db.Integer, primary_key=True)

    # 基本信息
    trip_no = db.Column(db.String(50), unique=True, nullable=False, index=True)  # 出差编号
    engineer = db.Column(db.String(100), nullable=False)  # 工程师姓名

    # 供应商信息
    supplier_code = db.Column(db.String(50), index=True)  # 供应商代码
    supplier_name = db.Column(db.String(200), nullable=False, index=True)  # 供应商名称
    supplier_location = db.Column(db.String(200))  # 供应商地址

    # 出差信息
    purpose = db.Column(db.Text, nullable=False)  # 出差目的（审核类型）
    start_date = db.Column(db.Date, nullable=False, index=True)  # 出发日期
    end_date = db.Column(db.Date, nullable=False)  # 返回日期
    days = db.Column(db.Integer)  # 出差天数

    # 审核类型
    audit_type = db.Column(db.String(50))  # initial/periodic/special/follow_up

    # 状态管理
    status = db.Column(db.String(20), default='pending')  # pending/approved/completed/cancelled

    # 费用信息（可选）
    estimated_cost = db.Column(db.Float)  # 预估费用
    actual_cost = db.Column(db.Float)  # 实际费用

    # 备注
    notes = db.Column(db.Text)  # 备注说明

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联文档
    documents = db.relationship('TripDocument', backref='trip', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<BusinessTrip {self.trip_no}: {self.supplier_name}>'


class TripDocument(db.Model):
    """出差文档表"""
    __tablename__ = 'trip_documents'

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('business_trips.id'), nullable=False, index=True)

    # 文档信息
    doc_type = db.Column(db.String(50), nullable=False)  # 文档类型
    title = db.Column(db.String(200), nullable=False)  # 文档标题

    # 文件存储
    original_name = db.Column(db.String(255), nullable=False)  # 原始文件名
    stored_name = db.Column(db.String(255), nullable=False)  # 存储文件名
    rel_path = db.Column(db.String(500), nullable=False)  # 相对路径

    # 文件属性
    mime = db.Column(db.String(100))  # MIME 类型
    size = db.Column(db.Integer)  # 文件大小（字节）

    # 备注
    remark = db.Column(db.Text)  # 备注说明

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TripDocument {self.title}>'


class KnowledgeItem(db.Model):
    """工艺知识条目"""
    __tablename__ = 'knowledge_items'

    id = db.Column(db.Integer, primary_key=True)

    # 基本信息
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # 工艺分类
    process = db.Column(db.String(50), nullable=False, index=True)

    # 优先级
    priority = db.Column(db.String(20), default='normal')

    # 标签（以逗号分隔的字符串）
    tags = db.Column(db.String(500))

    # 关联信息
    supplier_name = db.Column(db.String(200))
    part_number = db.Column(db.String(100))

    # 案例类型
    case_type = db.Column(db.String(50))

    # 附件和链接
    attachments = db.Column(db.Text)
    related_links = db.Column(db.Text)

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<KnowledgeItem {self.title}>'

    def get_tags_list(self):
        """获取标签列表"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []

    def set_tags_list(self, tags_list):
        """设置标签列表"""
        if tags_list:
            # 确保 tags_list 是列表
            if isinstance(tags_list, str):
                tags_list = [tags_list]
            self.tags = ','.join([str(tag).strip() for tag in tags_list if str(tag).strip()])
        else:
            self.tags = None

    @property
    def tags_display(self):
        """用于模板显示的标签列表（已处理为列表）"""
        return self.get_tags_list()


class FileLibrary(db.Model):
    """文件库"""
    __tablename__ = 'file_library'

    id = db.Column(db.Integer, primary_key=True)

    # 文件信息
    title = db.Column(db.String(200), nullable=False, index=True)  # 文件标题
    description = db.Column(db.Text)  # 文件描述
    category = db.Column(db.String(50), nullable=False, index=True)  # 文件分类
    # standard(标准), checklist(检查表), specification(规范), template(模板),
    # procedure(程序文件), manual(手册), other(其他)

    # 文件存储信息
    original_name = db.Column(db.String(255), nullable=False)  # 原始文件名
    stored_name = db.Column(db.String(255), nullable=False)  # 存储文件名
    rel_path = db.Column(db.String(500), nullable=False)  # 相对路径
    mime = db.Column(db.String(100))  # MIME 类型
    size = db.Column(db.Integer)  # 文件大小(字节)

    # 分类标签
    tags = db.Column(db.String(500))  # 标签（逗号分隔）

    # 版本信息
    version = db.Column(db.String(50))  # 版本号
    issue_date = db.Column(db.Date)  # 发布日期

    # 关联信息
    related_process = db.Column(db.String(50))  # 关联工艺
    supplier_name = db.Column(db.String(200))  # 关联供应商
    part_category = db.Column(db.String(100))  # 零件类别

    # 访问统计
    download_count = db.Column(db.Integer, default=0)  # 下载次数
    view_count = db.Column(db.Integer, default=0)  # 查看次数

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<FileLibrary {self.title}>'

    def get_tags_list(self):
        """获取标签列表"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []