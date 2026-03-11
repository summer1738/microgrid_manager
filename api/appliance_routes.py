import os
import sys
from typing import Any, Dict

from flask import Blueprint, jsonify, request

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database import (
    load_appliances,
    add_appliance_db,
    delete_appliance_db,
    set_appliance_shed_db,
    get_appliance,
)


appliance_bp = Blueprint("appliances", __name__, url_prefix="/appliances")


def _appliance_to_dict(a) -> Dict[str, Any]:
    return a.to_dict()


@appliance_bp.route("/", methods=["GET"])
def list_appliances():
    appliances = load_appliances()
    return jsonify([_appliance_to_dict(a) for a in appliances])


@appliance_bp.route("/", methods=["POST"])
def create_appliance():
    data = request.get_json(force=True) or {}
    name = data.get("name")
    power_w = data.get("power_w")
    priority = data.get("priority")

    if not name or power_w is None or priority is None:
        return jsonify({"error": "name, power_w, and priority are required"}), 400

    try:
        power_w = float(power_w)
        priority = int(priority)
    except (TypeError, ValueError):
        return jsonify({"error": "power_w must be float, priority must be int"}), 400

    if priority not in (1, 2, 3):
        return jsonify({"error": "priority must be 1, 2, or 3"}), 400

    household = (data.get("household") or "").strip() or None
    new = add_appliance_db(name=name, power_w=power_w, priority=priority, household=household)
    return jsonify(_appliance_to_dict(new)), 201


@appliance_bp.route("/<appliance_id>", methods=["DELETE"])
def remove_appliance(appliance_id: str):
    ok = delete_appliance_db(appliance_id)
    if not ok:
        return jsonify({"error": "appliance not found"}), 404
    return jsonify({"status": "deleted", "id": appliance_id})


@appliance_bp.route("/<appliance_id>/shed", methods=["PATCH"])
def shed_appliance(appliance_id: str):
    data = request.get_json(silent=True) or {}
    shed = data.get("shed", True)
    ok = set_appliance_shed_db(appliance_id, bool(shed))
    if not ok:
        return jsonify({"error": "appliance not found"}), 404
    a = get_appliance(appliance_id)
    return jsonify(_appliance_to_dict(a))

