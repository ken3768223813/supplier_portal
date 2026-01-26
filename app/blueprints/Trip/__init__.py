from flask import Blueprint

trip_bp = Blueprint(
    'trip',
    __name__,
    url_prefix='/trip'
)

from . import routes