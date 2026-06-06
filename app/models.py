from datetime import datetime
from .extensions import db
from sqlalchemy import CheckConstraint

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
    pn = db.Column(db.String(128), nullable=False, index=True)
    description = db.Column(db.Text)
    project = db.Column(db.String(128))
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ✅ 添加复合唯一约束
    __table_args__ = (
        db.UniqueConstraint('supplier_id', 'pn', name='uq_supplier_part_number'),
    )


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

    debit_ref = db.Column(db.String(100), nullable=True)
    debit_amount = db.Column(db.Float, nullable=True)
    debit_currency = db.Column(db.String(10), default='EUR')
    debit_date = db.Column(db.String(20), nullable=True)

    issue_summary = db.Column(db.Text, nullable=True)

    eight_d_root_cause = db.Column(db.Text)
    eight_d_action = db.Column(db.Text)

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
    status = db.Column(db.String(20), default='planning')  # pending/approved/completed/cancelled

    # 费用信息（可选）
    estimated_cost = db.Column(db.Float)  # 预估费用
    actual_cost = db.Column(db.Float)  # 实际费用

    # 备注
    notes = db.Column(db.Text)  # 备注说明

    local_folder_path = db.Column(db.Text, nullable=True)

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


"""
Audit Findings Database Models
审核发现数据库模型
"""

class AuditReport(db.Model):
    """审核报告主表"""
    __tablename__ = 'audit_reports'

    id = db.Column(db.Integer, primary_key=True)

    # 基本信息
    audit_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    audit_type = db.Column(db.String(50), default='ANFIA')  # ANFIA, SQA, etc.

    # 供应商信息
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    supplier_name = db.Column(db.String(255), nullable=False, index=True)

    # 审核信息
    audit_date = db.Column(db.Date, nullable=False, index=True)
    auditor = db.Column(db.String(100), nullable=False)  # 审核员

    # 文件信息
    original_filename = db.Column(db.String(255))
    stored_filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))

    # 统计信息
    total_findings = db.Column(db.Integer, default=0)  # 总问题数
    open_findings = db.Column(db.Integer, default=0)  # 未关闭问题数
    closed_findings = db.Column(db.Integer, default=0)  # 已关闭问题数

    # 状态
    status = db.Column(db.String(30), default='open')  # open, in_progress, closed

    # 备注
    notes = db.Column(db.Text)

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    findings = db.relationship('AuditFinding', backref='report', lazy='dynamic',
                               cascade='all, delete-orphan')

    def __repr__(self):
        return f'<AuditReport {self.audit_no}>'

    def update_statistics(self):
        """更新统计信息"""
        self.total_findings = self.findings.count()
        self.open_findings = self.findings.filter_by(status='open').count() + \
                             self.findings.filter_by(status='in_progress').count()
        self.closed_findings = self.findings.filter_by(status='closed').count()

        # 如果所有问题都关闭，报告状态改为 closed
        if self.total_findings > 0 and self.closed_findings == self.total_findings:
            self.status = 'closed'
        elif self.open_findings > 0:
            self.status = 'in_progress'


class AuditFinding(db.Model):
    """审核发现/问题点表"""
    __tablename__ = 'audit_findings'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('audit_reports.id'),
                          nullable=False, index=True)

    # 条款信息
    section = db.Column(db.String(100))  # Section 1, 2, 3, 4
    clause_no = db.Column(db.String(50))  # 1.1, 2.3, etc.
    clause_title = db.Column(db.String(255))  # 条款标题
    requirement = db.Column(db.Text)  # 要求描述

    # 问题描述
    finding = db.Column(db.Text, nullable=False)  # 发现的问题
    evidence = db.Column(db.Text)  # 证据

    # 严重程度
    severity = db.Column(db.String(20), default='minor')
    # critical, major, minor, observation

    # 供应商回复
    supplier_response = db.Column(db.Text)  # 供应商回复
    root_cause = db.Column(db.Text)  # 根本原因
    corrective_action = db.Column(db.Text)  # 纠正措施
    preventive_action = db.Column(db.Text)  # 预防措施

    # 责任人和时间
    responsible_person = db.Column(db.String(100))  # 供应商负责人
    target_date = db.Column(db.Date)  # 目标完成日期
    actual_completion_date = db.Column(db.Date)  # 实际完成日期

    # 状态
    status = db.Column(db.String(30), default='open', nullable=False, index=True)
    # open: 未开始
    # in_progress: 进行中
    # pending_verification: 待验证
    # closed: 已关闭

    # SQE 验证
    verification_date = db.Column(db.Date)  # 验证日期
    verification_result = db.Column(db.String(50))  # pass, fail
    verification_notes = db.Column(db.Text)  # 验证备注

    # 进展更新
    progress_updates = db.relationship('FindingProgress', backref='finding',
                                       lazy='dynamic', cascade='all, delete-orphan',
                                       order_by='FindingProgress.created_at.desc()')

    # 附件
    attachments = db.relationship('FindingAttachment', backref='finding',
                                  lazy='dynamic', cascade='all, delete-orphan')

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<AuditFinding {self.clause_no}: {self.status}>'

    @property
    def is_overdue(self):
        """是否逾期"""
        if self.status in ['closed'] or not self.target_date:
            return False
        return datetime.now().date() > self.target_date

    @property
    def days_until_due(self):
        """距离到期天数"""
        if not self.target_date:
            return None
        delta = self.target_date - datetime.now().date()
        return delta.days


class FindingProgress(db.Model):
    """问题点进展更新记录"""
    __tablename__ = 'finding_progress'

    id = db.Column(db.Integer, primary_key=True)
    finding_id = db.Column(db.Integer, db.ForeignKey('audit_findings.id'),
                           nullable=False, index=True)

    # 更新内容
    update_type = db.Column(db.String(50), nullable=False)
    # status_change, supplier_update, sqe_comment, verification

    old_status = db.Column(db.String(30))
    new_status = db.Column(db.String(30))

    comment = db.Column(db.Text)  # 更新说明
    updated_by = db.Column(db.String(100))  # 更新人

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<FindingProgress {self.update_type}>'


class FindingAttachment(db.Model):
    """问题点附件"""
    __tablename__ = 'finding_attachments'

    id = db.Column(db.Integer, primary_key=True)
    finding_id = db.Column(db.Integer, db.ForeignKey('audit_findings.id'),
                           nullable=False, index=True)

    # 附件信息
    title = db.Column(db.String(255))
    attachment_type = db.Column(db.String(50))  # photo, document, evidence

    # 文件信息
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    rel_path = db.Column(db.String(500), nullable=False)
    mime = db.Column(db.String(100))
    size = db.Column(db.Integer)

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<FindingAttachment {self.title}>'


"""
Task Management Database Models
任务管理数据库模型
"""


class Task(db.Model):
    """任务管理表"""
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)

    # 基本信息
    task_no = db.Column(db.String(50), unique=True, nullable=False, index=True)  # TASK-2026-001
    title = db.Column(db.String(255), nullable=False, index=True)  # 任务标题
    description = db.Column(db.Text)  # 详细描述

    # 来源信息
    source = db.Column(db.String(50), nullable=False, index=True)
    # boss_request(上级指示), customer_complaint(客户投诉),
    # supplier_issue(供应商问题), internal_audit(内部审核), other(其他)

    source_reference = db.Column(db.String(255))  # 来源引用（邮件主题、会议名称等）
    requester = db.Column(db.String(100))  # 任务发起人

    # 分类
    category = db.Column(db.String(50), index=True)
    # quality_issue(质量问题), supplier_audit(供应商审核),
    # documentation(文档工作), training(培训), meeting(会议), other(其他)

    # 优先级
    priority = db.Column(db.String(20), default='medium', nullable=False, index=True)
    # urgent(紧急), high(高), medium(中), low(低)

    # 时间管理
    due_date = db.Column(db.Date, index=True)  # 截止日期
    start_date = db.Column(db.Date)  # 开始日期
    completed_date = db.Column(db.Date)  # 完成日期

    # 状态
    status = db.Column(db.String(30), default='pending', nullable=False, index=True)
    # pending(待处理), in_progress(进行中), on_hold(暂停),
    # completed(已完成), cancelled(已取消)

    # 进度
    progress = db.Column(db.Integer, default=0)  # 完成百分比 0-100

    # 关联信息（可选）
    related_supplier = db.Column(db.String(255))  # 关联供应商
    related_tr_no = db.Column(db.String(50))  # 关联 TR 编号
    related_audit_no = db.Column(db.String(50))  # 关联审核编号
    related_trip_no = db.Column(db.String(50))  # 关联出差编号

    # 工作量估算
    estimated_hours = db.Column(db.Float)  # 预计工时
    actual_hours = db.Column(db.Float)  # 实际工时

    # 备注和附件
    notes = db.Column(db.Text)  # 备注

    # 提醒设置
    reminder_enabled = db.Column(db.Boolean, default=True)  # 是否开启提醒
    reminder_days_before = db.Column(db.Integer, default=1)  # 提前几天提醒

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    updates = db.relationship('TaskUpdate', backref='task', lazy='dynamic',
                              cascade='all, delete-orphan',
                              order_by='TaskUpdate.created_at.desc()')

    attachments = db.relationship('TaskAttachment', backref='task', lazy='dynamic',
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Task {self.task_no}: {self.title}>'

    @property
    def is_overdue(self):
        """是否逾期"""
        if self.status in ['completed', 'cancelled'] or not self.due_date:
            return False
        return datetime.now().date() > self.due_date

    @property
    def days_until_due(self):
        """距离到期天数"""
        if not self.due_date:
            return None
        delta = self.due_date - datetime.now().date()
        return delta.days

    @property
    def is_urgent_reminder(self):
        """是否需要紧急提醒（即将到期）"""
        if not self.reminder_enabled or not self.due_date:
            return False
        if self.status in ['completed', 'cancelled']:
            return False
        days_left = self.days_until_due
        if days_left is None:
            return False
        return 0 <= days_left <= self.reminder_days_before


class TaskUpdate(db.Model):
    """任务进展更新记录"""
    __tablename__ = 'task_updates'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'),
                        nullable=False, index=True)

    # 更新内容
    update_type = db.Column(db.String(50), nullable=False)
    # status_change(状态变更), progress_update(进度更新),
    # comment(评论), milestone(里程碑)

    old_status = db.Column(db.String(30))  # 旧状态
    new_status = db.Column(db.String(30))  # 新状态

    old_progress = db.Column(db.Integer)  # 旧进度
    new_progress = db.Column(db.Integer)  # 新进度

    content = db.Column(db.Text)  # 更新内容
    updated_by = db.Column(db.String(100))  # 更新人

    created_at = db.Column(db.DateTime, default=datetime.utcnow,
                           nullable=False, index=True)

    def __repr__(self):
        return f'<TaskUpdate {self.update_type}>'


class TaskAttachment(db.Model):
    """任务附件"""
    __tablename__ = 'task_attachments'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'),
                        nullable=False, index=True)

    # 附件信息
    title = db.Column(db.String(255))
    attachment_type = db.Column(db.String(50))  # email, document, photo, other

    # 文件信息
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    rel_path = db.Column(db.String(500), nullable=False)
    mime = db.Column(db.String(100))
    size = db.Column(db.Integer)

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<TaskAttachment {self.title}>'


# ... 你之前的 Supplier, Part, Document 等类保持不变 ...

class EDCReport(db.Model):
    """
    SAP EDC PDF 报告数据模型
    用于存储从 OneDrive 扫描提取的质量报告信息
    """
    __tablename__ = "edc_reports"

    # 1. 报告核心识别信息 (主键)
    report_no = db.Column(db.String(50), primary_key=True)

    # 2. 报告分类 (Quality Classification)
    classification = db.Column(db.String(100), nullable=True, index=True)

    # 3. 报告日期 (重要修改：设为 nullable=True 以兼容缺失日期的报告)
    report_date = db.Column(db.Date, nullable=True, index=True)

    # 4. 供应商关联信息
    supplier_code = db.Column(db.String(64), index=True)  # PDF 中的 Supplier Code
    supplier_name = db.Column(db.String(255))           # PDF 中的 Rif./Ditta 名称
    # 逻辑关联外键
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)

    # 5. 零部件/图纸信息
    drawing = db.Column(db.String(128), index=True)      # PDF 中的 Drawing
    part_name = db.Column(db.String(255))               # PDF 中的 Description
    # 逻辑关联外键
    part_id = db.Column(db.Integer, db.ForeignKey("parts.id"), nullable=True)

    # 6. 质量数据
    rejected_parts = db.Column(db.Integer, default=0)
    received_parts = db.Column(db.Integer, default=0)

    # 7. 问题描述 (存储红框内的多行文本，包括后续页)
    removals = db.Column(db.Text)

    # 8. 系统与文件管理信息
    file_path = db.Column(db.String(500), nullable=False)
    has_task = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 定义关系
    supplier_rel = db.relationship("Supplier", backref=db.backref("edc_reports", lazy="dynamic"))
    part_rel = db.relationship("Part", backref=db.backref("edc_reports", lazy="dynamic"))

    def __repr__(self):
        return f"<EDCReport {self.report_no} - {self.drawing}>"

    @property
    def severity_color(self):
        """根据不合格数量返回颜色级别"""
        if not self.rejected_parts: return "green"
        if self.rejected_parts > 50: return "red"
        return "orange"


# ── 在 models.py 末尾追加以下内容 ──────────────────────────────────────────

class NodeStandard(db.Model):
    """
    思维导图节点 ↔ 公司标准/文件 关联表
    将 knowledge 思维导图的某个节点与 FileLibrary 中的文档或自定义标准绑定
    """
    __tablename__ = "node_standards"

    id           = db.Column(db.Integer, primary_key=True)
    process      = db.Column(db.String(50),  nullable=False, index=True)   # 工艺 slug, e.g. "casting"
    node_id      = db.Column(db.String(100), nullable=False, index=True)   # 节点 id,   e.g. "hpdc"

    # 关联方式 A：指向 FileLibrary 中已上传的文件
    file_id      = db.Column(db.Integer, db.ForeignKey("file_library.id"), nullable=True)

    # 关联方式 B：手动填写自定义标准（不一定有文件）
    std_code     = db.Column(db.String(100), nullable=True)   # 标准号, e.g. "GB/T 15115"
    std_name     = db.Column(db.String(255), nullable=True)   # 标准名称
    std_type     = db.Column(db.String(50),  nullable=True)   # 类型: 国标/企业标准/客户标准 …
    std_link     = db.Column(db.String(500), nullable=True)   # 外部链接（可选）

    # 备注
    remark       = db.Column(db.Text, nullable=True)

    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # 关系
    file         = db.relationship("FileLibrary", backref=db.backref("node_standards", lazy="dynamic"))

    __table_args__ = (
        db.Index("ix_node_std_lookup", "process", "node_id"),
    )

    def __repr__(self):
        return f"<NodeStandard {self.process}/{self.node_id} → {self.std_code or self.file_id}>"

    def to_dict(self):
        d = {
            "id":       self.id,
            "process":  self.process,
            "node_id":  self.node_id,
            "std_code": self.std_code,
            "std_name": self.std_name,
            "std_type": self.std_type,
            "std_link": self.std_link,
            "remark":   self.remark,
            "file_id":  self.file_id,
        }
        if self.file:
            d["file_title"]    = self.file.title
            d["file_category"] = self.file.category
        return d


class NodeKnowledgeLink(db.Model):
    """
    思维导图节点 ↔ KnowledgeItem 关联表
    将某个节点与已有的知识条目绑定，方便从节点直接跳转相关知识
    """
    __tablename__ = "node_knowledge_links"

    id           = db.Column(db.Integer, primary_key=True)
    process      = db.Column(db.String(50),  nullable=False, index=True)
    node_id      = db.Column(db.String(100), nullable=False, index=True)
    knowledge_id = db.Column(db.Integer, db.ForeignKey("knowledge_items.id"),
                             nullable=False, index=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    knowledge    = db.relationship("KnowledgeItem",
                                   backref=db.backref("node_links", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("process", "node_id", "knowledge_id", name="uq_node_knowledge"),
    )

    def __repr__(self):
        return f"<NodeKnowledgeLink {self.process}/{self.node_id} → KI#{self.knowledge_id}>"

    def to_dict(self):
        return {
            "id":            self.id,
            "process":       self.process,
            "node_id":       self.node_id,
            "knowledge_id":  self.knowledge_id,
            "knowledge_title": self.knowledge.title if self.knowledge else None,
            "knowledge_process": self.knowledge.process if self.knowledge else None,
        }

# ── 追加到 app/models.py 末尾 ──────────────────────────────────────────────
# Control Plan 三张新表

class ControlPlan(db.Model):
    """
    控制计划主表
    层级: Supplier → Part → ControlPlan（一个 Part 一份 CP）
    """
    __tablename__ = 'control_plans'

    id           = db.Column(db.Integer, primary_key=True)
    supplier_id  = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False, index=True)
    part_id      = db.Column(db.Integer, db.ForeignKey('parts.id'),     nullable=False, index=True)

    cp_no        = db.Column(db.String(50), unique=True, nullable=False, index=True)
    # 生成规则示例: CP-SUP001-PN12345  (供应商code + 零件号)

    revision     = db.Column(db.String(20), default='A0')
    status       = db.Column(db.String(20), default='active', index=True)
    # active / draft / obsolete

    # 工艺大类 —— 用于"同类零件"筛选对比
    process_type = db.Column(db.String(50), index=True)
    # casting(铸造) / stamping(冲压) / injection(注塑)
    # machining(机加工) / welding(焊接) / assembly(装配) / other

    audit_date   = db.Column(db.Date)       # 审核日期（到供应商现场时填）
    auditor      = db.Column(db.String(100))  # 审核员（你自己名字）
    notes        = db.Column(db.Text)

    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    steps        = db.relationship(
        'ProcessStep', backref='control_plan',
        lazy='dynamic', cascade='all, delete-orphan',
        order_by='ProcessStep.seq'
    )
    supplier = db.relationship('Supplier', backref=db.backref('control_plans', lazy='dynamic'))
    part     = db.relationship('Part',     backref=db.backref('control_plans', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('supplier_id', 'part_id', 'process_type', name='uq_cp_supplier_part_process'),
    )

    def __repr__(self):
        return f'<ControlPlan {self.cp_no}>'

    def total_steps(self):
        return self.steps.count()

    def key_steps(self):
        return self.steps.filter_by(is_key_process=True).count()


class ProcessStep(db.Model):
    """
    工序步骤表
    一个 CP 下按 seq 顺序排列多道工序
    """
    __tablename__ = 'process_steps'

    id              = db.Column(db.Integer, primary_key=True)
    cp_id           = db.Column(db.Integer, db.ForeignKey('control_plans.id'), nullable=False, index=True)

    seq             = db.Column(db.Integer, nullable=False)     # 顺序号 10, 20, 30 … 便于插入
    process_name    = db.Column(db.String(100), nullable=False) # 工序名：压铸 / T6热处理 / 机加工
    process_code    = db.Column(db.String(50))                  # 工序编号（供应商自己的编号）
    machine         = db.Column(db.String(100))                 # 设备/工具名称
    is_key_process  = db.Column(db.Boolean, default=False)      # 关键工序 KPC flag

    notes           = db.Column(db.Text)

    # 子特性（每道工序下可有多个控制特性行）
    characteristics = db.relationship(
        'ControlCharacteristic', backref='step',
        lazy='dynamic', cascade='all, delete-orphan',
        order_by='ControlCharacteristic.id'
    )

    def __repr__(self):
        return f'<ProcessStep {self.seq}: {self.process_name}>'

    def char_count(self):
        return self.characteristics.count()


class ControlCharacteristic(db.Model):
    """
    控制特性表（AIAG Control Plan 的每一数据行）
    一道工序下可有多个控制特性（温度、压力、时间……）
    """
    __tablename__ = 'control_characteristics'

    id             = db.Column(db.Integer, primary_key=True)
    step_id        = db.Column(db.Integer, db.ForeignKey('process_steps.id'), nullable=False, index=True)

    char_name      = db.Column(db.String(150), nullable=False)  # 特性名称：模具温度
    spec_value     = db.Column(db.String(100))  # 规格值（数值或文本）：220
    spec_unit      = db.Column(db.String(30))   # 单位：°C / MPa / mm / s
    tolerance      = db.Column(db.String(50))   # 公差：±10 / +0.05/-0.02
    control_method = db.Column(db.String(150))  # 控制方法：热电偶 / 游标卡尺
    sample_size    = db.Column(db.String(50))   # 抽样量：3件
    frequency      = db.Column(db.String(50))   # 检验频次：每批次 / 每小时 / 连续
    reaction_plan  = db.Column(db.Text)         # 超差反应计划
    is_key_char    = db.Column(db.Boolean, default=False)  # 关键特性 KCC flag

    def __repr__(self):
        return f'<ControlCharacteristic {self.char_name}: {self.spec_value}{self.spec_unit}>'

    def spec_display(self):
        """返回完整规格显示字符串，如 220°C ±10"""
        parts = []
        if self.spec_value:
            parts.append(self.spec_value)
        if self.spec_unit:
            parts.append(self.spec_unit)
        if self.tolerance:
            parts.append(self.tolerance)
        return ' '.join(parts)