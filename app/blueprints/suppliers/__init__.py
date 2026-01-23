from flask import Blueprint

suppliers_bp = Blueprint("suppliers", __name__)

from . import routes  # noqa

