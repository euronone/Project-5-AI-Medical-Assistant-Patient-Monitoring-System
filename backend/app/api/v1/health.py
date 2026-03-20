from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__, url_prefix="/health")


@health_bp.route("", methods=["GET"])
def health_check():
    """Basic health check endpoint."""
    return jsonify({"status": "ok", "version": "1.0"}), 200
