"""pydantic extra='forbid' (mass assignment) and the login rate limiter (no database)."""

import uuid

import pytest
from pydantic import ValidationError

from m5_backend.app import models
from m5_backend.app.ratelimit import LoginRateLimiter

U = str(uuid.uuid4())


@pytest.mark.parametrize(
    ("model", "body"),
    [
        (models.HouseholdIn, {"assigned_asha_id": U}),
        (models.HouseholdIn, {"facility_id": U}),
        (models.HouseholdIn, {"role": "physician"}),
        (
            models.PatientIn,
            {
                "household_id": U,
                "name_synthetic": "SYNTHETIC-X",
                "age_band": "25-34",
                "sex": "F",
                "facility_id": U,
            },
        ),
        (models.EncounterIn, {"patient_id": U, "encounter_type": "nurse_consult", "author_id": U}),
        (
            models.EncounterIn,
            {"patient_id": U, "encounter_type": "nurse_consult", "role": "physician"},
        ),
        (models.RecordUpdate, {"record": {}, "status": "saved"}),
        (models.RecordUpdate, {"record": {}, "approved_by": U}),
        (
            models.OrderIn,
            {
                "encounter_id": U,
                "drug": "paracetamol",
                "dose_value": 500,
                "dose_unit": "mg",
                "frequency_per_day": 3,
                "duration_days": 3,
                "status": "draft",
                "patient_id": U,
            },
        ),
        (models.ActivePatientIn, {"patient_id": U, "facility_id": U}),
        (models.LoginIn, {"username": U, "password": "x", "role": "physician"}),
    ],
)
def test_extra_fields_forbidden(model, body):
    with pytest.raises(ValidationError):
        model.model_validate(body)


@pytest.mark.parametrize("bad", ["SYNTHETIC-x'; DROP TABLE clinic.patients; --", "Real Name", ""])
def test_patient_name_must_be_synthetic_pattern(bad):
    with pytest.raises(ValidationError):
        models.PatientIn.model_validate(
            {"household_id": U, "name_synthetic": bad, "age_band": "25-34", "sex": "F"}
        )


@pytest.mark.parametrize("bad", ["paracetamol'; --", "PARACETAMOL", "x" * 80, "1 OR 1=1"])
def test_drug_pattern(bad):
    with pytest.raises(ValidationError):
        models.OrderIn.model_validate(
            {
                "encounter_id": U,
                "drug": bad,
                "dose_value": 500,
                "dose_unit": "mg",
                "frequency_per_day": 3,
                "duration_days": 3,
                "status": "draft",
            }
        )


def test_order_status_cannot_be_injected():
    with pytest.raises(ValidationError):
        models.OrderUpdate.model_validate({"status": "ready_to_dispense' OR '1'='1"})


def test_rate_limiter_blocks_after_max_and_recovers():
    t = [0.0]
    rl = LoginRateLimiter(max_attempts=5, window_s=60, clock=lambda: t[0])
    assert all(rl.allow("ip|user") for _ in range(5))
    assert not rl.allow("ip|user")
    assert rl.allow("ip|other-user")  # keys are independent
    t[0] = 61.0
    assert rl.allow("ip|user")
