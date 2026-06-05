from flask import render_template, request, jsonify, current_app
from . import edc_bp
from app.models import EDCReport
from app.utils.edc_processor import start_sync_background, get_sync_state


@edc_bp.route('/')
def index():
    search         = request.args.get('search', '').strip()
    date_from      = request.args.get('date_from', '')
    date_to        = request.args.get('date_to', '')
    classification = request.args.get('classification', '').strip()
    page           = request.args.get('page', 1, type=int)

    query = EDCReport.query

    if search:
        query = query.filter(
            EDCReport.drawing.contains(search) |
            EDCReport.report_no.contains(search) |
            EDCReport.supplier_name.contains(search) |
            EDCReport.supplier_code.contains(search)
        )
    if date_from:
        query = query.filter(EDCReport.report_date >= date_from)
    if date_to:
        query = query.filter(EDCReport.report_date <= date_to)
    if classification:
        query = query.filter(EDCReport.classification == classification)

    pagination  = query.order_by(EDCReport.report_date.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    total_count = EDCReport.query.count()

    return render_template(
        'edc/index.html',
        reports=pagination.items,
        pagination=pagination,
        total_count=total_count,
        search=search,
        date_from=date_from,
        date_to=date_to,
        classification=classification,
    )


@edc_bp.route('/sync/start', methods=['POST'])
def sync_start():
    app = current_app._get_current_object()
    if start_sync_background(app):
        return jsonify({"status": "started"})
    return jsonify({"status": "already_running"})


@edc_bp.route('/sync/progress')
def sync_progress():
    return jsonify(get_sync_state())