from typing import Optional
from app.extensions import db
from app.models.user import User
from app.models.doctor import DoctorProfile


def get_doctors(
    page: int = 1,
    per_page: int = 20,
    specialization: Optional[str] = None,
    department: Optional[str] = None,
    available_for_telemedicine: Optional[bool] = None,
) -> dict:
    """
    Return a paginated list of doctors with optional filters.
    All authenticated users can list doctors (patients browse, admins manage).
    """
    query = (
        db.session.query(DoctorProfile)
        .join(User, DoctorProfile.user_id == User.id)
        .filter(User.is_active == True)
    )

    if specialization:
        query = query.filter(
            DoctorProfile.specialization.ilike(f"%{specialization.strip()}%")
        )

    if department:
        query = query.filter(
            DoctorProfile.department.ilike(f"%{department.strip()}%")
        )

    if available_for_telemedicine is not None:
        query = query.filter(
            DoctorProfile.available_for_telemedicine == available_for_telemedicine
        )

    total = query.count()
    doctors = (
        query.order_by(User.last_name.asc(), User.first_name.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "doctors": doctors,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def get_doctor_by_id(doctor_id: str) -> Optional[DoctorProfile]:
    """Return a single doctor profile with joined user info."""
    return (
        db.session.query(DoctorProfile)
        .join(User, DoctorProfile.user_id == User.id)
        .filter(DoctorProfile.id == doctor_id)
        .first()
    )


def update_doctor(
    doctor_id: str,
    data: dict,
    current_user: User,
) -> Optional[DoctorProfile]:
    """
    Update doctor profile fields.

    - Doctors can only update their own profile.
    - Admins can update any doctor profile.
    """
    doctor = get_doctor_by_id(doctor_id)
    if doctor is None:
        return None

    # Access control
    if current_user.role == "doctor" and doctor.user_id != current_user.id:
        return None

    # Fields that belong on DoctorProfile
    profile_fields = {
        "specialization",
        "department",
        "hospital_affiliation",
        "years_of_experience",
        "consultation_fee",
        "available_for_telemedicine",
        "bio",
    }

    # Fields that belong on User
    user_fields = {"first_name", "last_name", "phone"}

    for field in profile_fields:
        value = data.get(field)
        if value is not None:
            setattr(doctor, field, value)

    for field in user_fields:
        value = data.get(field)
        if value is not None:
            setattr(doctor.user, field, value)

    db.session.commit()
    db.session.refresh(doctor)
    return doctor
