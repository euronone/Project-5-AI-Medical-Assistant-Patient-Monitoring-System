from marshmallow import Schema, fields, validate, EXCLUDE


class UserBasicSchema(Schema):
    """Minimal user info embedded inside doctor responses."""

    class Meta:
        unknown = EXCLUDE

    id = fields.UUID(dump_only=True)
    email = fields.Email(dump_only=True)
    first_name = fields.Str(dump_only=True)
    last_name = fields.Str(dump_only=True)
    phone = fields.Str(dump_only=True, allow_none=True)
    avatar_url = fields.Str(dump_only=True, allow_none=True)
    role = fields.Str(dump_only=True)
    is_active = fields.Bool(dump_only=True)


class DoctorProfileSchema(Schema):
    """Full doctor profile — used for GET /doctors/:id responses."""

    class Meta:
        unknown = EXCLUDE

    id = fields.UUID(dump_only=True)
    user_id = fields.UUID(dump_only=True)
    license_number = fields.Str(dump_only=True)
    specialization = fields.Str(dump_only=True)
    department = fields.Str(dump_only=True, allow_none=True)
    hospital_affiliation = fields.Str(dump_only=True, allow_none=True)
    years_of_experience = fields.Int(dump_only=True, allow_none=True)
    consultation_fee = fields.Decimal(dump_only=True, allow_none=True, as_string=True)
    available_for_telemedicine = fields.Bool(dump_only=True)
    bio = fields.Str(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    # Nested user info (joined)
    user = fields.Nested(UserBasicSchema, dump_only=True)


class DoctorUpdateSchema(Schema):
    """Accepted fields for PUT /doctors/:id."""

    class Meta:
        unknown = EXCLUDE

    specialization = fields.Str(
        validate=validate.Length(min=1, max=200), load_default=None
    )
    department = fields.Str(validate=validate.Length(max=200), load_default=None)
    hospital_affiliation = fields.Str(
        validate=validate.Length(max=300), load_default=None
    )
    years_of_experience = fields.Int(
        validate=validate.Range(min=0, max=70), load_default=None
    )
    consultation_fee = fields.Decimal(places=2, load_default=None)
    available_for_telemedicine = fields.Bool(load_default=None)
    bio = fields.Str(load_default=None)
    # User-level fields doctors can update
    first_name = fields.Str(validate=validate.Length(min=1, max=100), load_default=None)
    last_name = fields.Str(validate=validate.Length(min=1, max=100), load_default=None)
    phone = fields.Str(validate=validate.Length(max=20), load_default=None)


class DoctorListSchema(Schema):
    """Shape of GET /doctors list response."""

    class Meta:
        unknown = EXCLUDE

    doctors = fields.List(fields.Nested(DoctorProfileSchema))
    total = fields.Int()
    page = fields.Int()
    per_page = fields.Int()
