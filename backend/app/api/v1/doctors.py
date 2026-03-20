from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.models.user import User
from app.schemas.doctor_schema import (
    DoctorProfileSchema,
    DoctorUpdateSchema,
    DoctorListSchema,
)
from app.services import doctor_service

doctors_bp = Blueprint("doctors", __name__, url_prefix="/doctors")

profile_schema = DoctorProfileSchema()
list_schema = DoctorListSchema()
update_schema = DoctorUpdateSchema()


def _get_current_user() -> User:
    """Helper — fetch the User row for the JWT caller."""
    user_id = get_jwt_identity()
    return User.query.get(user_id)


# ---------------------------------------------------------------------------
# GET /api/v1/doctors
# ---------------------------------------------------------------------------
@doctors_bp.route("", methods=["GET"])
@jwt_required()
def list_doctors():
    """
    List doctors with optional filters.

    Query params:
      - page                      (int, default 1)
      - per_page                  (int, default 20, max 100)
      - specialization            (str, optional)
      - department                (str, optional)
      - available_for_telemedicine (bool, optional) — pass true/false

    Access: all authenticated users.
    """
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    specialization = request.args.get("specialization", None)
    department = request.args.get("department", None)

    # Parse boolean query param
    tele_param = request.args.get("available_for_telemedicine", None)
    available_for_telemedicine = None
    if tele_param is not None:
        available_for_telemedicine = tele_param.lower() in ("true", "1", "yes")

    result = doctor_service.get_doctors(
        page=page,
        per_page=per_page,
        specialization=specialization,
        department=department,
        available_for_telemedicine=available_for_telemedicine,
    )

    return jsonify(list_schema.dump(result)), 200


# ---------------------------------------------------------------------------
# GET /api/v1/doctors/<doctor_id>
# ---------------------------------------------------------------------------
@doctors_bp.route("/<uuid:doctor_id>", methods=["GET"])
@jwt_required()
def get_doctor(doctor_id):
    """
    Full doctor profile with joined user info.

    Access: all authenticated users.
    """
    doctor = doctor_service.get_doctor_by_id(str(doctor_id))

    if doctor is None:
        return jsonify({"error": "Doctor not found"}), 404

    return jsonify(profile_schema.dump(doctor)), 200


# ---------------------------------------------------------------------------
# PUT /api/v1/doctors/<doctor_id>
# ---------------------------------------------------------------------------
@doctors_bp.route("/<uuid:doctor_id>", methods=["PUT"])
@jwt_required()
def update_doctor(doctor_id):
    """
    Update doctor profile fields.

    Access:
      - doctor → can update their own profile only
      - admin  → can update any doctor profile
      - others → 403
    """
    current_user = _get_current_user()

    if current_user.role not in ("admin", "doctor"):
        return jsonify({"error": "Forbidden"}), 403

    body = request.get_json(silent=True) or {}

    try:
        data = update_schema.load(body)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 422

    # Remove keys that were not sent (None load_defaults)
    data = {k: v for k, v in data.items() if v is not None}

    if not data:
        return jsonify({"error": "No valid fields provided"}), 400

    doctor = doctor_service.update_doctor(
        doctor_id=str(doctor_id),
        data=data,
        current_user=current_user,
    )

    if doctor is None:
        return jsonify({"error": "Doctor not found or access denied"}), 404

    return jsonify(profile_schema.dump(doctor)), 200
