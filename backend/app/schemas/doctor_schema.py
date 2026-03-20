from __future__ import annotations
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, EmailStr


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


class DoctorProfileSchema(BaseModel):
    """Response schema for a full doctor profile."""
    id: UUID
    user_id: UUID
    license_number: str
    specialization: str
    department: Optional[str] = None
    hospital_affiliation: Optional[str] = None
    years_of_experience: Optional[int] = None
    consultation_fee: Optional[Decimal] = None
    available_for_telemedicine: bool
    bio: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    user: UserBasicSchema

    model_config = {"from_attributes": True}


class DoctorUpdateSchema(BaseModel):
    """Request body for PUT /doctors/:id."""
    specialization: Optional[str] = None
    department: Optional[str] = None
    hospital_affiliation: Optional[str] = None
    years_of_experience: Optional[int] = None
    consultation_fee: Optional[Decimal] = None
    available_for_telemedicine: Optional[bool] = None
    bio: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class DoctorListSchema(BaseModel):
    """Response schema for GET /doctors."""
    doctors: List[DoctorProfileSchema]
    total: int
    page: int
    per_page: int
