import uuid
from datetime import datetime
from app.extensions import db


class DoctorProfile(db.Model):
    __tablename__ = "doctor_profiles"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    license_number = db.Column(db.String(100), unique=True, nullable=False)
    specialization = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(200))
    hospital_affiliation = db.Column(db.String(300))
    years_of_experience = db.Column(db.Integer)
    consultation_fee = db.Column(db.Numeric(10, 2))
    available_for_telemedicine = db.Column(db.Boolean, default=True)
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = db.relationship("User", back_populates="doctor_profile", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<DoctorProfile user_id={self.user_id} specialization={self.specialization}>"
