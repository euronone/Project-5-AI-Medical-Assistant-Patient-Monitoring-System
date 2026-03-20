from flask import Blueprint
from app.api.v1.patients import patients_bp
from app.api.v1.doctors import doctors_bp
from app.api.v1.health import health_bp

v1_bp = Blueprint("v1", __name__, url_prefix="/v1")

v1_bp.register_blueprint(patients_bp)
v1_bp.register_blueprint(doctors_bp)
v1_bp.register_blueprint(health_bp)
