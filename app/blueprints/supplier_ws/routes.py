from flask import render_template, abort
from ...models import Supplier
from flask import render_template, abort, redirect, url_for


def get_supplier_or_404(supplier_code: str) -> Supplier:
    s = Supplier.query.filter_by(code=supplier_code).first()
    if not s:
        abort(404)
    return s

from . import supplier_ws_bp

@supplier_ws_bp.route("/<supplier_code>/")
def overview(supplier_code):
    # 默认进入零部件列表页（企业后台列表页）
    return redirect(url_for("parts.list_parts", supplier_code=supplier_code))

