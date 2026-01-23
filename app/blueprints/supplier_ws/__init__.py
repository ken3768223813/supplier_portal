from flask import Blueprint
supplier_ws_bp = Blueprint("supplier_ws", __name__, url_prefix="/suppliers")
from . import routes  # noqa
