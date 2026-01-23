from flask import Blueprint
parts_bp = Blueprint("parts", __name__, url_prefix="/suppliers/<supplier_code>/parts")
from . import routes  # noqa
