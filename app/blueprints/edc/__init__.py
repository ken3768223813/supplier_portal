from flask import Blueprint

edc_bp = Blueprint('edc', __name__)

from app.blueprints.edc import routes  # ← 加这一行就够了