from flask import Flask
from app.config import config_map
from app.extensions import db, migrate, jwt, socketio, cors


def create_app(env: str = "development") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_map[env])

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    socketio.init_app(app, cors_allowed_origins="*")

    # Register blueprints
    from app.api import api_bp
    app.register_blueprint(api_bp)

    # Import models so Alembic can detect them
    from app.models import User, PatientProfile, DoctorProfile  # noqa: F401

    return app
