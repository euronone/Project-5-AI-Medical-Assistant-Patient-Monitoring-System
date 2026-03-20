import uuid
from datetime import datetime
from app.extensions import db


class PatientProfile(db.Model):
    __tablename__ = "patient_profiles"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(20))
    blood_type = db.Column(db.String(5))
    height_cm = db.Column(db.Numeric(5, 2))
    weight_kg = db.Column(db.Numeric(5, 2))
    emergency_contact_name = db.Column(db.String(200))
    emergency_contact_phone = db.Column(db.String(20))
    insurance_provider = db.Column(db.String(200))
    insurance_policy_number = db.Column(db.String(100))
    primary_physician_id = db.Column(
        db.UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = db.relationship("User", back_populates="patient_profile", foreign_keys=[user_id])
    primary_physician = db.relationship("User", foreign_keys=[primary_physician_id])

    def __repr__(self) -> str:
        return f"<PatientProfile user_id={self.user_id}>"
