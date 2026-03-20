from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError

from app.models.user import User
from app.schemas.patient_schema import (
    PatientProfileSchema,
    PatientUpdateSchema,
    PatientListSchema,
)
from app.services import patient_service

patients_bp = Blueprint("patients", __name__, url_prefix="/patients")

profile_schema = PatientProfileSchema()
list_schema = PatientListSchema()
update_schema = PatientUpdateSchema()


def _get_current_user() -> User:
    """Helper — fetch the User row for the JWT caller."""
    user_id = get_jwt_identity()
    return User.query.get(user_id)


# ---------------------------------------------------------------------------
# GET /api/v1/patients
# ---------------------------------------------------------------------------
@patients_bp.route("", methods=["GET"])
@jwt_required()
def list_patients():
    """
    List patients with pagination and optional search.

    Query params:
      - page       (int, default 1)
      - per_page   (int, default 20, max 100)
      - search     (str, optional) — searches first name, last name, email

    Access:
      - admin  → all patients
      - doctor → their assigned patients only
      - patient / nurse → 403
    """
    current_user = _get_current_user()

    if current_user.role not in ("admin", "doctor"):
        return jsonify({"error": "Forbidden"}), 403

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    search = request.args.get("search", None)

    result = patient_service.get_patients(
        current_user=current_user,
        page=page,
        per_page=per_page,
        search=search,
    )

    return jsonify(list_schema.dump(result)), 200


# ---------------------------------------------------------------------------
# GET /api/v1/patients/<patient_id>
# ---------------------------------------------------------------------------
@patients_bp.route("/<uuid:patient_id>", methods=["GET"])
@jwt_required()
def get_patient(patient_id):
    """
    Full patient profile with joined user info.

    Access:
      - patient → own profile only
      - doctor  → their assigned patients only
      - admin   → any patient
    """
    current_user = _get_current_user()

    if current_user.role not in ("admin", "doctor", "patient"):
        return jsonify({"error": "Forbidden"}), 403

    patient = patient_service.get_patient_by_id(
        patient_id=str(patient_id),
        current_user=current_user,
    )

    if patient is None:
        return jsonify({"error": "Patient not found or access denied"}), 404

    return jsonify(profile_schema.dump(patient)), 200


# ---------------------------------------------------------------------------
# PUT /api/v1/patients/<patient_id>
# ---------------------------------------------------------------------------
@patients_bp.route("/<uuid:patient_id>", methods=["PUT"])
@jwt_required()
def update_patient(patient_id):
    """
    Update patient profile fields.

    Access:
      - patient → can update their own profile only
      - admin   → can update any patient profile
      - doctor  → read-only, cannot update patient profiles
    """
    current_user = _get_current_user()

    if current_user.role not in ("admin", "patient"):
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

    patient = patient_service.update_patient(
        patient_id=str(patient_id),
        data=data,
        current_user=current_user,
    )

    if patient is None:
        return jsonify({"error": "Patient not found or access denied"}), 404

    return jsonify(profile_schema.dump(patient)), 200
