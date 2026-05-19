from io import BytesIO

from flask import Blueprint, abort, jsonify, render_template, request, send_file

from app.database import get_db
from app.pdf.sacs import generate_sacs_pdf
from app.pdf.tcc import generate_tcc_pdf
from app.services import (
    delete_client,
    get_client_bundle,
    get_report,
    latest_report_balances,
    list_clients,
    list_reports,
    save_client,
    save_report,
)

web_bp = Blueprint("web", __name__)
api_bp = Blueprint("api", __name__)


@web_bp.route("/")
def index():
    return render_template("index.html")


@web_bp.route("/clients/new")
def client_new():
    return render_template("client_form.html", client=None)


@web_bp.route("/clients/<int:client_id>")
def client_detail(client_id):
    return render_template("client_detail.html", client_id=client_id)


@web_bp.route("/clients/<int:client_id>/edit")
def client_edit(client_id):
    return render_template("client_form.html", client_id=client_id)


@web_bp.route("/clients/<int:client_id>/report")
def report_entry(client_id):
    return render_template("report_entry.html", client_id=client_id)


@web_bp.route("/clients/<int:client_id>/reports/<int:report_id>")
def report_view(client_id, report_id):
    return render_template("report_complete.html", client_id=client_id, report_id=report_id)


@api_bp.route("/clients", methods=["GET"])
def api_list_clients():
    return jsonify(list_clients(get_db()))


@api_bp.route("/clients/<int:client_id>", methods=["GET"])
def api_get_client(client_id):
    bundle = get_client_bundle(get_db(), client_id)
    if not bundle:
        abort(404)
    bundle["previous_balances"] = latest_report_balances(get_db(), client_id)
    bundle["reports"] = list_reports(get_db(), client_id)
    return jsonify(bundle)


@api_bp.route("/clients", methods=["POST"])
def api_create_client():
    data = request.get_json(force=True)
    client_id = save_client(get_db(), data)
    return jsonify({"id": client_id}), 201


@api_bp.route("/clients/<int:client_id>", methods=["PUT"])
def api_update_client(client_id):
    data = request.get_json(force=True)
    data["id"] = client_id
    save_client(get_db(), data)
    return jsonify({"id": client_id})


@api_bp.route("/clients/<int:client_id>", methods=["DELETE"])
def api_delete_client(client_id):
    delete_client(get_db(), client_id)
    return "", 204


@api_bp.route("/clients/<int:client_id>/reports", methods=["POST"])
def api_create_report(client_id):
    data = request.get_json(force=True)
    try:
        report_id, calculations = save_report(get_db(), client_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"id": report_id, "calculations": calculations}), 201


@api_bp.route("/reports/<int:report_id>", methods=["GET"])
def api_get_report(report_id):
    payload = get_report(get_db(), report_id)
    if not payload:
        abort(404)
    return jsonify(payload)


@api_bp.route("/reports/<int:report_id>/pdf/<report_type>", methods=["GET"])
def api_download_pdf(report_id, report_type):
    payload = get_report(get_db(), report_id)
    if not payload:
        abort(404)

    if report_type == "sacs":
        pdf_bytes = generate_sacs_pdf(payload)
        filename = f"SACS_{payload['client']['display_name']}_{payload['report']['quarter_label']}.pdf"
    elif report_type == "tcc":
        pdf_bytes = generate_tcc_pdf(payload)
        filename = f"TCC_{payload['client']['display_name']}_{payload['report']['quarter_label']}.pdf"
    else:
        abort(404)

    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename.replace(" ", "_"),
    )


@api_bp.route("/clients/<int:client_id>/preview", methods=["POST"])
def api_preview_calculations(client_id):
    from app.calculations import compute_report, validate_balances_complete

    bundle = get_client_bundle(get_db(), client_id)
    if not bundle:
        abort(404)
    balances = request.get_json(force=True).get("balances", {})
    missing = validate_balances_complete(bundle["client"], bundle["accounts"], balances)
    calculations = compute_report(bundle["client"], bundle["accounts"], balances)
    return jsonify({"calculations": calculations, "missing": missing})
