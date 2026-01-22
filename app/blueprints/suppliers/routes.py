from flask import render_template, request, redirect, url_for, flash
from ...extensions import db
from ...models import Supplier
from . import suppliers_bp

@suppliers_bp.get("/")
def index():
    q = request.args.get("q", "").strip()
    query = Supplier.query
    if q:
        like = f"%{q}%"
        query = query.filter((Supplier.code.like(like)) | (Supplier.name.like(like)))
    suppliers = query.order_by(Supplier.is_active.desc(), Supplier.code.asc()).all()
    return render_template("suppliers/index.html", suppliers=suppliers, q=q)

@suppliers_bp.post("/add")
def add():
    code = request.form.get("code", "").strip()
    name = request.form.get("name", "").strip()
    if not code or not name:
        flash("Supplier code 和 name 都需要填写。", "warning")
        return redirect(url_for("suppliers.index"))

    exists = Supplier.query.filter_by(code=code).first()
    if exists:
        flash(f"供应商 {code} 已存在。", "warning")
        return redirect(url_for("suppliers.index"))

    db.session.add(Supplier(code=code, name=name))
    db.session.commit()
    flash(f"已添加供应商：{code}", "success")
    return redirect(url_for("suppliers.index"))
