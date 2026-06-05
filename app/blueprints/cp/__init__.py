from flask import Blueprint

cp_bp = Blueprint(name="cp", import_name=__name__, url_prefix="/cp")
from . import routes  # noqa