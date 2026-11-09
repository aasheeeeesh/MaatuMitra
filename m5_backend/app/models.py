"""Request bodies. Every model forbids unknown fields (blocks mass assignment of role,
assigned_asha_id, facility_id, author_id, approved_by, patient_id ...). Server-owned fields
(who, which facility, approval) are filled from the verified token, never from the body."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AgeBand = Literal["0-4", "5-14", "15-24", "25-34", "35-44", "45-59", "60+"]
Sex = Literal["F", "M", "X"]
EncounterType = Literal[
    "asha_household_visit", "nurse_consult", "physician_consult", "pharmacist_dispensing"
]
DoseUnit = Literal["mg", "g", "mcg", "ml", "tablet", "capsule", "sachet", "drop", "teaspoon", "IU"]
OrderStatus = Literal["draft", "ready_to_dispense", "cancelled"]

SYNTHETIC_NAME = r"^SYNTHETIC-[A-Za-z0-9]{1,40}(-[A-Za-z0-9]{1,40}){0,3}$"
DRUG = r"^[a-z][a-z0-9-]{0,40}( [a-z0-9-]{1,40}){0,3}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LoginIn(Strict):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class HouseholdIn(Strict):
    """Empty on purpose: facility and assigned ASHA come from the token."""


class PatientIn(Strict):
    household_id: uuid.UUID
    name_synthetic: str = Field(pattern=SYNTHETIC_NAME, max_length=120)
    age_band: AgeBand
    sex: Sex


class PatientUpdate(Strict):
    name_synthetic: str | None = Field(default=None, pattern=SYNTHETIC_NAME, max_length=120)
    age_band: AgeBand | None = None
    sex: Sex | None = None


class EncounterIn(Strict):
    patient_id: uuid.UUID
    encounter_type: EncounterType


class EncounterUpdate(Strict):
    encounter_type: EncounterType


class RecordIn(Strict):
    encounter_id: uuid.UUID
    record: dict[str, Any]


class RecordUpdate(Strict):
    record: dict[str, Any]


class SaveIn(Strict):
    verdict: dict[str, Any]


class OrderIn(Strict):
    encounter_id: uuid.UUID
    drug: str = Field(pattern=DRUG, max_length=100)
    dose_value: float = Field(gt=0, le=100000)
    dose_unit: DoseUnit
    frequency_per_day: float = Field(gt=0, le=24)
    duration_days: float = Field(gt=0, le=365)
    status: OrderStatus = "draft"


class OrderUpdate(Strict):
    drug: str | None = Field(default=None, pattern=DRUG, max_length=100)
    dose_value: float | None = Field(default=None, gt=0, le=100000)
    dose_unit: DoseUnit | None = None
    frequency_per_day: float | None = Field(default=None, gt=0, le=24)
    duration_days: float | None = Field(default=None, gt=0, le=365)
    status: OrderStatus | None = None


class ActivePatientIn(Strict):
    patient_id: uuid.UUID
