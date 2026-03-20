"""
Seed the database with sample patients and doctors for development.

Usage:
    cd backend
    python scripts/seed_db.py
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bcrypt
from datetime import date
from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.patient import PatientProfile
from app.models.doctor import DoctorProfile


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


DOCTORS = [
    {
        "email": "dr.sarah.jones@medassist.com",
        "first_name": "Sarah",
        "last_name": "Jones",
        "phone": "+1-555-0101",
        "role": "doctor",
        "profile": {
            "license_number": "MD-001-2020",
            "specialization": "Cardiology",
            "department": "Cardiac Care",
            "hospital_affiliation": "MedAssist General Hospital",
            "years_of_experience": 12,
            "consultation_fee": 150.00,
            "available_for_telemedicine": True,
            "bio": "Board-certified cardiologist with 12 years of experience.",
        },
    },
    {
        "email": "dr.james.patel@medassist.com",
        "first_name": "James",
        "last_name": "Patel",
        "phone": "+1-555-0102",
        "role": "doctor",
        "profile": {
            "license_number": "MD-002-2018",
            "specialization": "General Practice",
            "department": "Primary Care",
            "hospital_affiliation": "MedAssist General Hospital",
            "years_of_experience": 8,
            "consultation_fee": 100.00,
            "available_for_telemedicine": True,
            "bio": "Family medicine specialist focused on preventive care.",
        },
    },
    {
        "email": "dr.lisa.chen@medassist.com",
        "first_name": "Lisa",
        "last_name": "Chen",
        "phone": "+1-555-0103",
        "role": "doctor",
        "profile": {
            "license_number": "MD-003-2015",
            "specialization": "Neurology",
            "department": "Neuroscience",
            "hospital_affiliation": "MedAssist General Hospital",
            "years_of_experience": 15,
            "consultation_fee": 200.00,
            "available_for_telemedicine": False,
            "bio": "Neurologist specializing in stroke and epilepsy management.",
        },
    },
]

PATIENTS = [
    {
        "email": "patient.alice@example.com",
        "first_name": "Alice",
        "last_name": "Morgan",
        "phone": "+1-555-1001",
        "role": "patient",
        "profile": {
            "date_of_birth": date(1985, 6, 15),
            "gender": "female",
            "blood_type": "A+",
            "height_cm": 165.0,
            "weight_kg": 62.5,
            "emergency_contact_name": "Bob Morgan",
            "emergency_contact_phone": "+1-555-1002",
            "insurance_provider": "BlueCross",
            "insurance_policy_number": "BC-123456",
        },
    },
    {
        "email": "patient.bob@example.com",
        "first_name": "Bob",
        "last_name": "Smith",
        "phone": "+1-555-2001",
        "role": "patient",
        "profile": {
            "date_of_birth": date(1972, 11, 3),
            "gender": "male",
            "blood_type": "O-",
            "height_cm": 178.0,
            "weight_kg": 82.0,
            "emergency_contact_name": "Jane Smith",
            "emergency_contact_phone": "+1-555-2002",
            "insurance_provider": "Aetna",
            "insurance_policy_number": "AE-789012",
        },
    },
    {
        "email": "patient.carol@example.com",
        "first_name": "Carol",
        "last_name": "White",
        "phone": "+1-555-3001",
        "role": "patient",
        "profile": {
            "date_of_birth": date(1990, 3, 22),
            "gender": "female",
            "blood_type": "B+",
            "height_cm": 160.0,
            "weight_kg": 55.0,
            "emergency_contact_name": "David White",
            "emergency_contact_phone": "+1-555-3002",
            "insurance_provider": "UnitedHealth",
            "insurance_policy_number": "UH-345678",
        },
    },
]

ADMIN = {
    "email": "admin@medassist.com",
    "first_name": "System",
    "last_name": "Admin",
    "phone": "+1-555-0001",
    "role": "admin",
}


def seed():
    print("Creating tables if they don't exist (Supabase)...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        default_password = hash_password("MedAssist@123")

        # Seed admin
        print("Seeding admin...")
        if not db.query(User).filter_by(email=ADMIN["email"]).first():
            admin_user = User(
                email=ADMIN["email"],
                password_hash=default_password,
                role=ADMIN["role"],
                first_name=ADMIN["first_name"],
                last_name=ADMIN["last_name"],
                phone=ADMIN["phone"],
                is_active=True,
                is_verified=True,
            )
            db.add(admin_user)
            db.flush()

        # Seed doctors
        print("Seeding doctors...")
        doctor_users = []
        for doc_data in DOCTORS:
            existing = db.query(User).filter_by(email=doc_data["email"]).first()
            if existing:
                doctor_users.append(existing)
                continue

            user = User(
                email=doc_data["email"],
                password_hash=default_password,
                role=doc_data["role"],
                first_name=doc_data["first_name"],
                last_name=doc_data["last_name"],
                phone=doc_data["phone"],
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.flush()

            profile = DoctorProfile(user_id=user.id, **doc_data["profile"])
            db.add(profile)
            doctor_users.append(user)

        db.flush()

        # Seed patients — assign to first doctor
        print("Seeding patients...")
        primary_physician = doctor_users[0]
        for pat_data in PATIENTS:
            if db.query(User).filter_by(email=pat_data["email"]).first():
                continue

            user = User(
                email=pat_data["email"],
                password_hash=default_password,
                role=pat_data["role"],
                first_name=pat_data["first_name"],
                last_name=pat_data["last_name"],
                phone=pat_data["phone"],
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.flush()

            profile = PatientProfile(
                user_id=user.id,
                primary_physician_id=primary_physician.id,
                **pat_data["profile"],
            )
            db.add(profile)

        db.commit()
        print("\nSeeding complete!")
        print("Default password for all accounts: MedAssist@123")
        print(f"Admin:   {ADMIN['email']}")
        for d in DOCTORS:
            print(f"Doctor:  {d['email']}")
        for p in PATIENTS:
            print(f"Patient: {p['email']}")

    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
