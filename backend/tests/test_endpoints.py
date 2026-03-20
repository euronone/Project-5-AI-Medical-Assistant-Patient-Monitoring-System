"""
Endpoint tests using FastAPI TestClient with mocked DB and auth.
Run: cd backend && venv/Scripts/pytest tests/test_endpoints.py -v
"""
import uuid
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta, UTC

from app import create_app
from app.models.user import User

app = create_app()
client = TestClient(app)

SECRET = "dev-jwt-secret-123"
ALGO = "HS256"


def make_token(user_id: str, role: str) -> str:
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": datetime.now(UTC) + timedelta(hours=1)},
        SECRET,
        algorithm=ALGO,
    )


def make_user(role: str) -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = f"{role}@test.com"
    u.first_name = role.capitalize()
    u.last_name = "Test"
    u.role = role
    u.is_active = True
    return u


def auth(role: str) -> dict:
    user = make_user(role)
    token = make_token(str(user.id), role)
    return {"headers": {"Authorization": f"Bearer {token}"}, "user": user}


# ─── Health ───────────────────────────────────────────────────────────────────

def test_health_no_auth():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": "1.0"}


# ─── Auth Guard ───────────────────────────────────────────────────────────────

def test_patients_no_token_returns_401():
    r = client.get("/api/v1/patients")
    assert r.status_code == 401

def test_patients_invalid_token_returns_401():
    r = client.get("/api/v1/patients", headers={"Authorization": "Bearer BADTOKEN"})
    assert r.status_code == 401

def test_doctors_no_token_returns_401():
    r = client.get("/api/v1/doctors")
    assert r.status_code == 401


# ─── Role-Based Access ────────────────────────────────────────────────────────

def _patched_client(role: str):
    """Return TestClient with get_current_user mocked for the given role."""
    from app.dependencies import get_current_user
    user = make_user(role)
    creds = auth(role)

    def override():
        return user

    app.dependency_overrides[get_current_user] = override
    return client, creds["headers"], user


def test_nurse_on_patients_returns_403():
    c, headers, _ = _patched_client("nurse")
    r = c.get("/api/v1/patients", headers=headers)
    app.dependency_overrides.clear()
    assert r.status_code == 403
    assert r.json()["detail"] == "Forbidden"


def test_patient_on_patients_list_returns_403():
    """
    Patient role should get 403 on GET /patients (list).
    Patients access their own profile via GET /patients/:id, not the list endpoint.
    Per spec: 'Doctors see their patients | admins see all.'
    """
    from app.dependencies import get_current_user
    user = make_user("patient")
    app.dependency_overrides[get_current_user] = lambda: user

    r = client.get("/api/v1/patients")
    app.dependency_overrides.clear()

    assert r.status_code == 403
    assert r.json()["detail"] == "Forbidden"


def test_admin_on_patients_allowed():
    from app.dependencies import get_current_user
    from app.database import get_db
    user = make_user("admin")

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = 0
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_db.query.return_value = mock_query

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db

    r = client.get("/api/v1/patients")
    app.dependency_overrides.clear()

    assert r.status_code == 200


def test_doctor_on_patients_allowed():
    from app.dependencies import get_current_user
    from app.database import get_db
    user = make_user("doctor")

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = 0
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_db.query.return_value = mock_query

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db

    r = client.get("/api/v1/patients")
    app.dependency_overrides.clear()

    assert r.status_code == 200


def test_all_roles_can_list_doctors():
    from app.dependencies import get_current_user
    from app.database import get_db

    for role in ("admin", "doctor", "patient", "nurse"):
        user = make_user(role)

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        app.dependency_overrides[get_current_user] = lambda u=user: u
        app.dependency_overrides[get_db] = lambda: mock_db

        r = client.get("/api/v1/doctors")
        app.dependency_overrides.clear()

        assert r.status_code == 200, f"Role {role} failed on GET /doctors"


# ─── Schema Validation ────────────────────────────────────────────────────────

def test_update_patient_invalid_gender_returns_422():
    from app.dependencies import get_current_user
    user = make_user("admin")
    app.dependency_overrides[get_current_user] = lambda: user

    r = client.put(
        f"/api/v1/patients/{uuid.uuid4()}",
        json={"gender": "INVALID_GENDER"},
    )
    app.dependency_overrides.clear()
    assert r.status_code == 422


def test_update_patient_invalid_blood_type_returns_422():
    from app.dependencies import get_current_user
    user = make_user("admin")
    app.dependency_overrides[get_current_user] = lambda: user

    r = client.put(
        f"/api/v1/patients/{uuid.uuid4()}",
        json={"blood_type": "XY+"},
    )
    app.dependency_overrides.clear()
    assert r.status_code == 422


def test_update_patient_empty_body_returns_400():
    from app.dependencies import get_current_user
    from app.database import get_db
    user = make_user("admin")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: MagicMock()

    r = client.put(f"/api/v1/patients/{uuid.uuid4()}", json={})
    app.dependency_overrides.clear()
    assert r.status_code == 400
    assert "No valid fields" in r.json()["detail"]


def test_update_doctor_empty_body_returns_400():
    from app.dependencies import get_current_user
    from app.database import get_db
    user = make_user("admin")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: MagicMock()

    r = client.put(f"/api/v1/doctors/{uuid.uuid4()}", json={})
    app.dependency_overrides.clear()
    assert r.status_code == 400


def test_get_patient_invalid_uuid_returns_422():
    from app.dependencies import get_current_user
    user = make_user("admin")
    app.dependency_overrides[get_current_user] = lambda: user

    r = client.get("/api/v1/patients/not-a-valid-uuid")
    app.dependency_overrides.clear()
    assert r.status_code == 422


def test_pagination_per_page_over_limit_returns_422():
    """
    FastAPI validates per_page with le=100.
    Sending per_page=9999 should return 422 Unprocessable Entity.
    """
    from app.dependencies import get_current_user
    user = make_user("admin")
    app.dependency_overrides[get_current_user] = lambda: user

    r = client.get("/api/v1/patients?page=1&per_page=9999")
    app.dependency_overrides.clear()

    assert r.status_code == 422


def test_pagination_valid_params_returns_200():
    """Valid pagination params should return 200."""
    from app.dependencies import get_current_user
    from app.database import get_db
    user = make_user("admin")

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = 5
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_db.query.return_value = mock_query

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db

    r = client.get("/api/v1/patients?page=2&per_page=10")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["page"] == 2
    assert r.json()["per_page"] == 10
    assert r.json()["total"] == 5


def test_doctor_cannot_update_another_doctors_profile():
    from app.dependencies import get_current_user
    from app.database import get_db

    doctor_user = make_user("doctor")
    other_doctor_id = uuid.uuid4()

    mock_db = MagicMock()
    mock_query = MagicMock()
    other_doctor = MagicMock()
    other_doctor.user_id = other_doctor_id  # different from doctor_user.id
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = other_doctor
    mock_db.query.return_value = mock_query

    app.dependency_overrides[get_current_user] = lambda: doctor_user
    app.dependency_overrides[get_db] = lambda: mock_db

    r = client.put(
        f"/api/v1/doctors/{other_doctor_id}",
        json={"specialization": "Hacking"},
    )
    app.dependency_overrides.clear()
    assert r.status_code == 404  # returns 404 because update_doctor returns None
