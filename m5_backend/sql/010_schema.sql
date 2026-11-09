-- 010_schema.sql  (run as owner_role)
-- Schemas, helper functions and tables. UUID keys only (gen_random_uuid, built into PG13+).
-- All data is SYNTHETIC: name columns must start with "SYNTHETIC-".

CREATE SCHEMA clinic;
CREATE SCHEMA research;
CREATE SCHEMA app;
REVOKE ALL ON SCHEMA clinic, research, app FROM PUBLIC;

-- Request context. Values are set per transaction by the API with
-- set_config(name, value, true) (= SET LOCAL). Empty / unset -> NULL -> policies match nothing.
-- A malformed value raises (cast error) -> the statement fails closed.
CREATE FUNCTION app.user_id() RETURNS uuid
  LANGUAGE sql STABLE PARALLEL SAFE
  AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;
CREATE FUNCTION app.facility_id() RETURNS uuid
  LANGUAGE sql STABLE PARALLEL SAFE
  AS $$ SELECT NULLIF(current_setting('app.facility_id', true), '')::uuid $$;
CREATE FUNCTION app.active_patient_id() RETURNS uuid
  LANGUAGE sql STABLE PARALLEL SAFE
  AS $$ SELECT NULLIF(current_setting('app.active_patient_id', true), '')::uuid $$;
REVOKE ALL ON FUNCTION app.user_id(), app.facility_id(), app.active_patient_id() FROM PUBLIC;

CREATE TABLE clinic.facilities (
  id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (name ~ '^SYNTHETIC-')
);

CREATE TABLE clinic.users (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role         text NOT NULL CHECK (role IN ('asha','nurse','physician','pharmacist','researcher')),
  facility_id  uuid REFERENCES clinic.facilities(id),
  display_name text NOT NULL CHECK (display_name ~ '^SYNTHETIC-')
);

CREATE TABLE clinic.households (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  facility_id      uuid NOT NULL REFERENCES clinic.facilities(id),
  assigned_asha_id uuid REFERENCES clinic.users(id),
  UNIQUE (id, facility_id)
);

CREATE TABLE clinic.patients (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id   uuid NOT NULL,
  facility_id    uuid NOT NULL REFERENCES clinic.facilities(id),
  name_synthetic text NOT NULL CHECK (name_synthetic ~ '^SYNTHETIC-'),
  age_band       text NOT NULL CHECK (age_band IN ('0-4','5-14','15-24','25-34','35-44','45-59','60+')),
  sex            text NOT NULL CHECK (sex IN ('F','M','X')),
  UNIQUE (id, facility_id),
  -- a patient lives in a household of the SAME facility (RI checks bypass RLS by design)
  FOREIGN KEY (household_id, facility_id) REFERENCES clinic.households(id, facility_id)
);

CREATE TABLE clinic.encounters (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id     uuid NOT NULL,
  author_id      uuid NOT NULL REFERENCES clinic.users(id),
  facility_id    uuid NOT NULL,
  encounter_type text NOT NULL CHECK (encounter_type IN
                   ('asha_household_visit','nurse_consult','physician_consult','pharmacist_dispensing')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, patient_id, facility_id),
  FOREIGN KEY (patient_id, facility_id) REFERENCES clinic.patients(id, facility_id)
);

CREATE TABLE clinic.records (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  encounter_id uuid NOT NULL REFERENCES clinic.encounters(id),
  json         jsonb NOT NULL,
  status       text NOT NULL CHECK (status IN ('draft','flagged','approved','saved')),
  approved_by  uuid REFERENCES clinic.users(id),
  approved_at  timestamptz,
  -- Saved-record gate in the DATABASE: nothing is 'saved' without an approver and a time.
  CONSTRAINT saved_requires_approval
    CHECK (status <> 'saved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))
);

CREATE TABLE clinic.medication_orders (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  encounter_id      uuid NOT NULL,
  patient_id        uuid NOT NULL,
  facility_id       uuid NOT NULL,
  drug              text NOT NULL CHECK (drug ~ '^[a-z][a-z0-9 -]{0,99}$'),
  dose_value        numeric NOT NULL CHECK (dose_value > 0),
  dose_unit         text NOT NULL CHECK (dose_unit IN
                      ('mg','g','mcg','ml','tablet','capsule','sachet','drop','teaspoon','IU')),
  frequency_per_day numeric NOT NULL CHECK (frequency_per_day > 0 AND frequency_per_day <= 24),
  duration_days     numeric NOT NULL CHECK (duration_days > 0 AND duration_days <= 365),
  status            text NOT NULL CHECK (status IN ('draft','ready_to_dispense','dispensed','cancelled')),
  -- the order's patient and facility must be the encounter's patient and facility
  FOREIGN KEY (encounter_id, patient_id, facility_id)
    REFERENCES clinic.encounters(id, patient_id, facility_id)
);

CREATE TABLE clinic.consents (
  patient_id  uuid PRIMARY KEY REFERENCES clinic.patients(id),
  research_ok boolean NOT NULL DEFAULT false,
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Audit log: enums and ids only. NO free-text column exists, so free text cannot be logged.
CREATE TABLE clinic.audit_log (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  at         timestamptz NOT NULL DEFAULT clock_timestamp(),
  user_id    uuid,
  app_role   text NOT NULL CHECK (app_role IN ('asha','nurse','physician','pharmacist','researcher','maint')),
  action     text NOT NULL CHECK (action IN ('select','list','insert','update','approve','save',
                 'save_rejected','set_active_patient','audio','export','seed')),
  table_name text NOT NULL CHECK (table_name IN ('facilities','users','households','patients',
                 'encounters','records','medication_orders','consents','audit_log','research_export',
                 'pharmacist_orders_v','audio')),
  row_id     uuid,
  outcome    text NOT NULL CHECK (outcome IN ('allow','deny','error'))
);

-- De-identified research table (filled ONLY by the export job). No ids from clinic.*.
CREATE TABLE research.encounters_deid (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),  -- fresh per export, unlinkable
  pseudonym        text NOT NULL CHECK (pseudonym ~ '^[0-9a-f]{20}$'),
  age_band         text NOT NULL,
  sex              text NOT NULL,
  encounter_type   text NOT NULL,
  encounter_month  text NOT NULL CHECK (encounter_month ~ '^[0-9]{4}-[0-9]{2}$'),
  record_status    text,
  symptoms_present text[] NOT NULL DEFAULT '{}',
  symptoms_absent  text[] NOT NULL DEFAULT '{}',
  medications      jsonb NOT NULL DEFAULT '[]'
);
