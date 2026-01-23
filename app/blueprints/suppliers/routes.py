from flask import render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError

from . import suppliers_bp
from ...extensions import db
from ...models import Supplier


@suppliers_bp.get("/")
def index():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Supplier.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Supplier.code.ilike(like)) |
            (Supplier.name.ilike(like)) |
            (Supplier.chinese_name.ilike(like))
        )

    query = query.order_by(Supplier.created_at.desc(), Supplier.code.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    suppliers = pagination.items

    return render_template(
        "suppliers/index.html",
        suppliers=suppliers,
        pagination=pagination,
        q=q,
        per_page=per_page,
    )


@suppliers_bp.post("/add")
def add():
    code = request.form.get("code", "").strip()
    name = request.form.get("name", "").strip()

    if not code or not name:
        flash("Supplier code 和 name 都需要填写。", "warning")
        return redirect(url_for("suppliers.index"))

    if Supplier.query.filter_by(code=code).first():
        flash(f"供应商 {code} 已存在。", "warning")
        return redirect(url_for("suppliers.index"))

    db.session.add(Supplier(code=code, name=name))
    db.session.commit()
    flash(f"已添加供应商：{code}", "success")
    return redirect(url_for("suppliers.index"))


@suppliers_bp.route("/new", methods=["GET", "POST"])
def new_supplier():
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        chinese_name = request.form.get("chinese_name", "").strip() or None


        if not code:
            flash("供应商代码不能为空", "error")
            return render_template("suppliers/new.html")

        if Supplier.query.filter_by(code=code).first():
            flash(f"供应商代码已存在：{code}", "error")
            return render_template("suppliers/new.html")

        s = Supplier(
            code=code,
            name=name,
            chinese_name=chinese_name,

        )
        db.session.add(s)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("保存失败：供应商代码可能重复", "error")
            return render_template("suppliers/new.html")

        flash("✅ 供应商已新增", "success")
        return redirect(url_for("suppliers.index"))

    return render_template("suppliers/new.html")


@suppliers_bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)

    if request.method == "POST":
        supplier.code = request.form.get("code", "").strip() or supplier.code
        supplier.name = request.form.get("name", "").strip() or supplier.name
        supplier.chinese_name = request.form.get("chinese_name", "").strip() or None


        db.session.commit()
        flash("已更新", "success")
        return redirect(url_for("suppliers.index"))

    return render_template("suppliers/edit.html", supplier=supplier)

@suppliers_bp.post("/<int:supplier_id>/delete")
def delete_supplier(supplier_id):
    s = Supplier.query.get_or_404(supplier_id)
    db.session.delete(s)
    db.session.commit()
    flash(f"已删除供应商：{s.code}", "success")
    return redirect(url_for("suppliers.index"))
