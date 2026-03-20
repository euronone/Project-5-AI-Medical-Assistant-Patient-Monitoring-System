from __future__ import annotations
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator


class UserBasicSchema(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class PatientProfileSchema(BaseModel):
    """Response schema for a full patient profile."""
    id: UUID
    user_id: UUID
    date_of_birth: date
    gender: Optional[str] = None
    blood_type: Optional[str] = None
    height_cm: Optional[Decimal] = None
    weight_kg: Optional[Decimal] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    primary_physician_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    user: UserBasicSchema

    model_config = {"from_attributes": True}


class PatientUpdateSchema(BaseModel):
    """Request body for PUT /patients/:id."""
    gender: Optional[str] = None
    blood_type: Optional[str] = None
    height_cm: Optional[Decimal] = None
    weight_kg: Optional[Decimal] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"male", "female", "other", "prefer_not_to_say"}
        if v is not None and v not in allowed:
            raise ValueError(f"gender must be one of {allowed}")
        return v

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
        if v is not None and v not in allowed:
            raise ValueError(f"blood_type must be one of {allowed}")
        return v


class PatientListSchema(BaseModel):
    """Response schema for GET /patients."""
    patients: List[PatientProfileSchema]
    total: int
    page: int
    per_page: int
