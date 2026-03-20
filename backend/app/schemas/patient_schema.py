from marshmallow import Schema, fields, validate, EXCLUDE


class UserBasicSchema(Schema):
    """Minimal user info embedded inside patient responses."""

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


class PatientProfileSchema(Schema):
    """Full patient profile — used for GET /patients/:id responses."""

    class Meta:
        unknown = EXCLUDE

    id = fields.UUID(dump_only=True)
    user_id = fields.UUID(dump_only=True)
    date_of_birth = fields.Date(dump_only=True)
    gender = fields.Str(dump_only=True, allow_none=True)
    blood_type = fields.Str(dump_only=True, allow_none=True)
    height_cm = fields.Decimal(dump_only=True, allow_none=True, as_string=True)
    weight_kg = fields.Decimal(dump_only=True, allow_none=True, as_string=True)
    emergency_contact_name = fields.Str(dump_only=True, allow_none=True)
    emergency_contact_phone = fields.Str(dump_only=True, allow_none=True)
    insurance_provider = fields.Str(dump_only=True, allow_none=True)
    insurance_policy_number = fields.Str(dump_only=True, allow_none=True)
    primary_physician_id = fields.UUID(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    # Nested user info (joined)
    user = fields.Nested(UserBasicSchema, dump_only=True)


class PatientUpdateSchema(Schema):
    """Accepted fields for PUT /patients/:id."""

    class Meta:
        unknown = EXCLUDE

    gender = fields.Str(
        validate=validate.OneOf(["male", "female", "other", "prefer_not_to_say"]),
        load_default=None,
    )
    blood_type = fields.Str(
        validate=validate.OneOf(["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]),
        load_default=None,
    )
    height_cm = fields.Decimal(places=2, load_default=None)
    weight_kg = fields.Decimal(places=2, load_default=None)
    emergency_contact_name = fields.Str(
        validate=validate.Length(max=200), load_default=None
    )
    emergency_contact_phone = fields.Str(
        validate=validate.Length(max=20), load_default=None
    )
    insurance_provider = fields.Str(
        validate=validate.Length(max=200), load_default=None
    )
    insurance_policy_number = fields.Str(
        validate=validate.Length(max=100), load_default=None
    )
    # User-level fields patients can update
    first_name = fields.Str(validate=validate.Length(min=1, max=100), load_default=None)
    last_name = fields.Str(validate=validate.Length(min=1, max=100), load_default=None)
    phone = fields.Str(validate=validate.Length(max=20), load_default=None)


class PatientListSchema(Schema):
    """Shape of GET /patients list response."""

    class Meta:
        unknown = EXCLUDE

    patients = fields.List(fields.Nested(PatientProfileSchema))
    total = fields.Int()
    page = fields.Int()
    per_page = fields.Int()
