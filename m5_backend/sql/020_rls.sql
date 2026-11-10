-- 020_rls.sql  (run as owner_role)
-- Row-level security written from PROJECT_BRIEF.md AGENT 6 (NOT from the expected-matrix file).
-- Every table: ENABLE + FORCE RLS. No policy = deny. One policy per role and action.
-- No policy is granted TO PUBLIC. DELETE is granted to no app role.

-- ---------------------------------------------------------------- RLS on every table
ALTER TABLE clinic.facilities        ENABLE ROW LEVEL SECURITY;  ALTER TABLE clinic.facilities        FORCE ROW LEVEL SECURITY;
ALTER TABLE clinic.users             ENABLE ROW LEVEL SECURITY;  ALTER TABLE clinic.users             FORCE ROW LEVEL SECURITY;
ALTER TABLE clinic.households        ENABLE ROW LEVEL SECURITY;  ALTER TABLE clinic.households        FORCE ROW LEVEL SECURITY;
ALTER TABLE clinic.patients          ENABLE ROW LEVEL SECURITY;  ALTER TABLE clinic.patients          FORCE ROW LEVEL SECURITY;
ALTER TABLE clinic.encounters        ENABLE ROW LEVEL SECURITY;  ALTER TABLE clinic.encounters        FORCE ROW LEVEL SECURITY;
ALTER TABLE clinic.records           ENABLE ROW LEVEL SECURITY;  ALTER TABLE clinic.records           FORCE ROW LEVEL SECURITY;
ALTER TABLE clinic.medication_orders ENABLE ROW LEVEL SECURITY;  ALTER TABLE clinic.medication_orders FORCE ROW LEVEL SECURITY;
ALTER TABLE clinic.consents          ENABLE ROW LEVEL SECURITY;  ALTER TABLE clinic.consents          FORCE ROW LEVEL SECURITY;
ALTER TABLE clinic.audit_log         ENABLE ROW LEVEL SECURITY;  ALTER TABLE clinic.audit_log         FORCE ROW LEVEL SECURITY;
ALTER TABLE research.encounters_deid ENABLE ROW LEVEL SECURITY;  ALTER TABLE research.encounters_deid FORCE ROW LEVEL SECURITY;
ALTER TABLE clinic.verdicts          ENABLE ROW LEVEL SECURITY;  ALTER TABLE clinic.verdicts          FORCE ROW LEVEL SECURITY;
ALTER TABLE clinic.record_resolutions ENABLE ROW LEVEL SECURITY; ALTER TABLE clinic.record_resolutions FORCE ROW LEVEL SECURITY;
ALTER TABLE research.pseudonym_map   ENABLE ROW LEVEL SECURITY;  ALTER TABLE research.pseudonym_map   FORCE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------- schema + helper access
REVOKE ALL ON ALL TABLES IN SCHEMA clinic, research FROM PUBLIC;
GRANT USAGE ON SCHEMA clinic TO asha_role, nurse_role, physician_role, pharmacist_role, maint_role, pharm_view_owner, audit_writer;
GRANT USAGE ON SCHEMA research TO researcher_role, maint_role;
GRANT USAGE ON SCHEMA app TO asha_role, nurse_role, physician_role, pharmacist_role, researcher_role, maint_role, pharm_view_owner, audit_writer;
GRANT EXECUTE ON FUNCTION app.user_id(), app.facility_id(), app.active_patient_id()
  TO asha_role, nurse_role, physician_role, pharmacist_role, researcher_role, maint_role, pharm_view_owner;
GRANT EXECUTE ON FUNCTION app.record_hash(jsonb) TO asha_role, nurse_role, physician_role, maint_role;

-- ================================================================ ASHA
-- "select/insert only on households where assigned_asha_id = her id, and on
--  patients/encounters/records reachable through those households"
GRANT SELECT, INSERT ON clinic.households, clinic.patients, clinic.encounters, clinic.records TO asha_role;

CREATE POLICY asha_households_select ON clinic.households FOR SELECT TO asha_role
  USING (assigned_asha_id = app.user_id());
CREATE POLICY asha_households_insert ON clinic.households FOR INSERT TO asha_role
  WITH CHECK (assigned_asha_id = app.user_id() AND facility_id = app.facility_id());

CREATE POLICY asha_patients_select ON clinic.patients FOR SELECT TO asha_role
  USING (EXISTS (SELECT 1 FROM clinic.households h
                 WHERE h.id = patients.household_id AND h.assigned_asha_id = app.user_id()));
CREATE POLICY asha_patients_insert ON clinic.patients FOR INSERT TO asha_role
  WITH CHECK (facility_id = app.facility_id()
              AND EXISTS (SELECT 1 FROM clinic.households h
                          WHERE h.id = patients.household_id AND h.assigned_asha_id = app.user_id()));

CREATE POLICY asha_encounters_select ON clinic.encounters FOR SELECT TO asha_role
  USING (EXISTS (SELECT 1 FROM clinic.patients p JOIN clinic.households h ON h.id = p.household_id
                 WHERE p.id = encounters.patient_id AND h.assigned_asha_id = app.user_id()));
CREATE POLICY asha_encounters_insert ON clinic.encounters FOR INSERT TO asha_role
  WITH CHECK (author_id = app.user_id()
              AND facility_id = app.facility_id()
              AND encounter_type = 'asha_household_visit'
              AND EXISTS (SELECT 1 FROM clinic.patients p JOIN clinic.households h ON h.id = p.household_id
                          WHERE p.id = encounters.patient_id AND h.assigned_asha_id = app.user_id()));

CREATE POLICY asha_records_select ON clinic.records FOR SELECT TO asha_role
  USING (EXISTS (SELECT 1 FROM clinic.encounters e
                   JOIN clinic.patients p ON p.id = e.patient_id
                   JOIN clinic.households h ON h.id = p.household_id
                 WHERE e.id = records.encounter_id AND h.assigned_asha_id = app.user_id()));
CREATE POLICY asha_records_insert ON clinic.records FOR INSERT TO asha_role
  WITH CHECK (status IN ('draft','flagged') AND approved_by IS NULL AND approved_at IS NULL
              AND EXISTS (SELECT 1 FROM clinic.encounters e
                            JOIN clinic.patients p ON p.id = e.patient_id
                            JOIN clinic.households h ON h.id = p.household_id
                          WHERE e.id = records.encounter_id AND h.assigned_asha_id = app.user_id()));

-- ================================================================ NURSE
-- "select/insert/update on patients, encounters, draft records in her facility;
--  read-only on medication_orders"   (draft = status draft or flagged, i.e. not yet approved)
GRANT SELECT, INSERT ON clinic.patients, clinic.encounters, clinic.records TO nurse_role;
GRANT UPDATE (name_synthetic, age_band, sex) ON clinic.patients TO nurse_role;
GRANT UPDATE (encounter_type) ON clinic.encounters TO nurse_role;
GRANT UPDATE (json, status) ON clinic.records TO nurse_role;
GRANT SELECT ON clinic.medication_orders TO nurse_role;

CREATE POLICY nurse_patients_select ON clinic.patients FOR SELECT TO nurse_role
  USING (facility_id = app.facility_id());
CREATE POLICY nurse_patients_insert ON clinic.patients FOR INSERT TO nurse_role
  WITH CHECK (facility_id = app.facility_id());
CREATE POLICY nurse_patients_update ON clinic.patients FOR UPDATE TO nurse_role
  USING (facility_id = app.facility_id()) WITH CHECK (facility_id = app.facility_id());

CREATE POLICY nurse_encounters_select ON clinic.encounters FOR SELECT TO nurse_role
  USING (facility_id = app.facility_id());
CREATE POLICY nurse_encounters_insert ON clinic.encounters FOR INSERT TO nurse_role
  WITH CHECK (facility_id = app.facility_id() AND author_id = app.user_id());
CREATE POLICY nurse_encounters_update ON clinic.encounters FOR UPDATE TO nurse_role
  USING (facility_id = app.facility_id()) WITH CHECK (facility_id = app.facility_id());

CREATE POLICY nurse_records_select ON clinic.records FOR SELECT TO nurse_role
  USING (status IN ('draft','flagged')
         AND EXISTS (SELECT 1 FROM clinic.encounters e
                     WHERE e.id = records.encounter_id AND e.facility_id = app.facility_id()));
CREATE POLICY nurse_records_insert ON clinic.records FOR INSERT TO nurse_role
  WITH CHECK (status IN ('draft','flagged') AND approved_by IS NULL AND approved_at IS NULL
              AND EXISTS (SELECT 1 FROM clinic.encounters e
                          WHERE e.id = records.encounter_id AND e.facility_id = app.facility_id()));
CREATE POLICY nurse_records_update ON clinic.records FOR UPDATE TO nurse_role
  USING (status IN ('draft','flagged')
         AND EXISTS (SELECT 1 FROM clinic.encounters e
                     WHERE e.id = records.encounter_id AND e.facility_id = app.facility_id()))
  WITH CHECK (status IN ('draft','flagged') AND approved_by IS NULL AND approved_at IS NULL
              AND EXISTS (SELECT 1 FROM clinic.encounters e
                          WHERE e.id = records.encounter_id AND e.facility_id = app.facility_id()));

CREATE POLICY nurse_orders_select ON clinic.medication_orders FOR SELECT TO nurse_role
  USING (facility_id = app.facility_id());

-- ================================================================ PHYSICIAN
-- "nurse rights plus insert/update medication_orders and approve records, in her facility"
GRANT SELECT, INSERT ON clinic.patients, clinic.encounters, clinic.records, clinic.medication_orders TO physician_role;
GRANT UPDATE (name_synthetic, age_band, sex) ON clinic.patients TO physician_role;
GRANT UPDATE (encounter_type) ON clinic.encounters TO physician_role;
GRANT UPDATE (json, status, approved_by, approved_at) ON clinic.records TO physician_role;
GRANT UPDATE (drug, dose_value, dose_unit, frequency_per_day, duration_days, status) ON clinic.medication_orders TO physician_role;

CREATE POLICY physician_patients_select ON clinic.patients FOR SELECT TO physician_role
  USING (facility_id = app.facility_id());
CREATE POLICY physician_patients_insert ON clinic.patients FOR INSERT TO physician_role
  WITH CHECK (facility_id = app.facility_id());
CREATE POLICY physician_patients_update ON clinic.patients FOR UPDATE TO physician_role
  USING (facility_id = app.facility_id()) WITH CHECK (facility_id = app.facility_id());

CREATE POLICY physician_encounters_select ON clinic.encounters FOR SELECT TO physician_role
  USING (facility_id = app.facility_id());
CREATE POLICY physician_encounters_insert ON clinic.encounters FOR INSERT TO physician_role
  WITH CHECK (facility_id = app.facility_id() AND author_id = app.user_id());
CREATE POLICY physician_encounters_update ON clinic.encounters FOR UPDATE TO physician_role
  USING (facility_id = app.facility_id()) WITH CHECK (facility_id = app.facility_id());

CREATE POLICY physician_records_select ON clinic.records FOR SELECT TO physician_role
  USING (EXISTS (SELECT 1 FROM clinic.encounters e
                 WHERE e.id = records.encounter_id AND e.facility_id = app.facility_id()));
CREATE POLICY physician_records_insert ON clinic.records FOR INSERT TO physician_role
  WITH CHECK (EXISTS (SELECT 1 FROM clinic.encounters e
                      WHERE e.id = records.encounter_id AND e.facility_id = app.facility_id())
              AND ((status IN ('draft','flagged') AND approved_by IS NULL AND approved_at IS NULL)
                   OR approved_by = app.user_id()));
-- A saved record is final: nobody can update it (USING excludes status 'saved').
-- Approval can only be in the physician's OWN name.
CREATE POLICY physician_records_update ON clinic.records FOR UPDATE TO physician_role
  USING (status <> 'saved'
         AND EXISTS (SELECT 1 FROM clinic.encounters e
                     WHERE e.id = records.encounter_id AND e.facility_id = app.facility_id()))
  WITH CHECK (EXISTS (SELECT 1 FROM clinic.encounters e
                      WHERE e.id = records.encounter_id AND e.facility_id = app.facility_id())
              AND ((status IN ('draft','flagged') AND approved_by IS NULL AND approved_at IS NULL)
                   OR approved_by = app.user_id()));

CREATE POLICY physician_orders_select ON clinic.medication_orders FOR SELECT TO physician_role
  USING (facility_id = app.facility_id());
CREATE POLICY physician_orders_insert ON clinic.medication_orders FOR INSERT TO physician_role
  WITH CHECK (facility_id = app.facility_id());
CREATE POLICY physician_orders_update ON clinic.medication_orders FOR UPDATE TO physician_role
  USING (facility_id = app.facility_id()) WITH CHECK (facility_id = app.facility_id());

-- ================================================================ PHARMACIST
-- NO base-table grants. Access only through clinic.pharmacist_orders_v (030_views.sql).

-- ================================================================ RESEARCHER
-- NO base-table grants. SELECT only on schema research.
GRANT SELECT ON research.encounters_deid TO researcher_role;
CREATE POLICY researcher_deid_select ON research.encounters_deid FOR SELECT TO researcher_role
  USING (true);

-- ================================================================ VERDICTS + RESOLUTIONS (F1 / D-80)
-- Verdicts are written by the API after the SERVER-SIDE verifier ran on the stored record.
-- A verdict is visible exactly when its record is visible (nested RLS on clinic.records).
-- No UPDATE / DELETE is granted to anyone (and triggers refuse them, see 050_gate.sql).
GRANT SELECT, INSERT ON clinic.verdicts TO asha_role, nurse_role, physician_role;
CREATE POLICY asha_verdicts_select ON clinic.verdicts FOR SELECT TO asha_role
  USING (EXISTS (SELECT 1 FROM clinic.records r WHERE r.id = verdicts.record_id));
CREATE POLICY nurse_verdicts_select ON clinic.verdicts FOR SELECT TO nurse_role
  USING (EXISTS (SELECT 1 FROM clinic.records r WHERE r.id = verdicts.record_id));
CREATE POLICY physician_verdicts_select ON clinic.verdicts FOR SELECT TO physician_role
  USING (EXISTS (SELECT 1 FROM clinic.records r WHERE r.id = verdicts.record_id));
CREATE POLICY asha_verdicts_insert ON clinic.verdicts FOR INSERT TO asha_role
  WITH CHECK (created_by = app.user_id() AND facility_id = app.facility_id()
              AND EXISTS (SELECT 1 FROM clinic.records r WHERE r.id = verdicts.record_id));
CREATE POLICY nurse_verdicts_insert ON clinic.verdicts FOR INSERT TO nurse_role
  WITH CHECK (created_by = app.user_id() AND facility_id = app.facility_id()
              AND EXISTS (SELECT 1 FROM clinic.records r WHERE r.id = verdicts.record_id));
CREATE POLICY physician_verdicts_insert ON clinic.verdicts FOR INSERT TO physician_role
  WITH CHECK (created_by = app.user_id() AND facility_id = app.facility_id()
              AND EXISTS (SELECT 1 FROM clinic.records r WHERE r.id = verdicts.record_id));

-- Only the approving physician writes resolutions, only in her own name and facility, only for
-- the CURRENT content of the record, and only for a verdict that belongs to that record.
GRANT SELECT, INSERT ON clinic.record_resolutions TO physician_role;
CREATE POLICY physician_resolutions_select ON clinic.record_resolutions FOR SELECT TO physician_role
  USING (facility_id = app.facility_id());
CREATE POLICY physician_resolutions_insert ON clinic.record_resolutions FOR INSERT TO physician_role
  WITH CHECK (resolved_by = app.user_id() AND facility_id = app.facility_id()
              AND record_hash = (SELECT app.record_hash(r.json) FROM clinic.records r
                                 WHERE r.id = record_resolutions.record_id)
              AND EXISTS (SELECT 1 FROM clinic.verdicts v
                          WHERE v.id = record_resolutions.verdict_id
                            AND v.record_id = record_resolutions.record_id));

-- ================================================================ MAINT (seed loader + export job)
-- Reachable only from owner_role (operator credentials), never from api_login.
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA clinic TO maint_role;
REVOKE INSERT ON clinic.audit_log FROM maint_role;   -- audit rows only via app.audit_write()
GRANT UPDATE (research_ok, updated_at) ON clinic.consents TO maint_role;
GRANT SELECT, INSERT, DELETE ON research.encounters_deid TO maint_role;

CREATE POLICY maint_facilities_select ON clinic.facilities        FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_facilities_insert ON clinic.facilities        FOR INSERT TO maint_role WITH CHECK (true);
CREATE POLICY maint_users_select      ON clinic.users             FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_users_insert      ON clinic.users             FOR INSERT TO maint_role WITH CHECK (true);
CREATE POLICY maint_households_select ON clinic.households        FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_households_insert ON clinic.households        FOR INSERT TO maint_role WITH CHECK (true);
CREATE POLICY maint_patients_select   ON clinic.patients          FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_patients_insert   ON clinic.patients          FOR INSERT TO maint_role WITH CHECK (true);
CREATE POLICY maint_encounters_select ON clinic.encounters        FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_encounters_insert ON clinic.encounters        FOR INSERT TO maint_role WITH CHECK (true);
CREATE POLICY maint_records_select    ON clinic.records           FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_records_insert    ON clinic.records           FOR INSERT TO maint_role WITH CHECK (true);
CREATE POLICY maint_orders_select     ON clinic.medication_orders FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_orders_insert     ON clinic.medication_orders FOR INSERT TO maint_role WITH CHECK (true);
CREATE POLICY maint_consents_select   ON clinic.consents          FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_consents_insert   ON clinic.consents          FOR INSERT TO maint_role WITH CHECK (true);
CREATE POLICY maint_consents_update   ON clinic.consents          FOR UPDATE TO maint_role USING (true) WITH CHECK (true);
CREATE POLICY maint_audit_select      ON clinic.audit_log         FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_deid_select       ON research.encounters_deid FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_deid_insert       ON research.encounters_deid FOR INSERT TO maint_role WITH CHECK (true);
CREATE POLICY maint_deid_delete       ON research.encounters_deid FOR DELETE TO maint_role USING (true);

CREATE POLICY maint_verdicts_select    ON clinic.verdicts            FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_resolutions_select ON clinic.record_resolutions  FOR SELECT TO maint_role USING (true);
-- private pseudonym map: maint_role only (the export job + the consent-withdrawal trigger)
GRANT SELECT, INSERT, DELETE ON research.pseudonym_map TO maint_role;
CREATE POLICY maint_pmap_select ON research.pseudonym_map FOR SELECT TO maint_role USING (true);
CREATE POLICY maint_pmap_insert ON research.pseudonym_map FOR INSERT TO maint_role WITH CHECK (true);
CREATE POLICY maint_pmap_delete ON research.pseudonym_map FOR DELETE TO maint_role USING (true);
