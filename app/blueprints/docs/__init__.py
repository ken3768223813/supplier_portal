from flask import Blueprint
docs_bp = Blueprint("docs", __name__, url_prefix="/suppliers/<supplier_code>/docs")
from . import routes  # noqa
