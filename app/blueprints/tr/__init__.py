from flask import Blueprint

tr_bp = Blueprint(
    "tr",
    __name__,
    template_folder="../../templates"
)

from . import routes  # 一定要有
