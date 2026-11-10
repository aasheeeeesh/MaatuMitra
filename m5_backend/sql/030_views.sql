-- 030_views.sql  (run as owner_role; owner_role may SET ROLE pharm_view_owner)
-- Pharmacist access: ONE security_barrier view, owned by the narrow role pharm_view_owner.
-- PG16 views default to security_invoker = false: the base table is read with the VIEW
-- OWNER's privileges and RLS policies. pharm_view_owner has exactly one policy (below), so the
-- predicate is enforced twice: in the view WHERE clause and in RLS.
-- Limit (documented): the database cannot prove the patient is physically present; it only
-- narrows scope to one active patient at the pharmacist's facility, and the API audits it.

GRANT SELECT (id, patient_id, facility_id, drug, dose_value, dose_unit, frequency_per_day,
              duration_days, status) ON clinic.medication_orders TO pharm_view_owner;

CREATE POLICY pharm_view_owner_orders_select ON clinic.medication_orders FOR SELECT TO pharm_view_owner
  USING (facility_id = app.facility_id()
         AND status = 'ready_to_dispense'
         AND patient_id = app.active_patient_id());

-- F8: patient_ref is a random per-patient reference (clinic.patients.ref), not a UUID prefix.
GRANT SELECT (id, ref, facility_id) ON clinic.patients TO pharm_view_owner;
CREATE POLICY pharm_view_owner_patients_select ON clinic.patients FOR SELECT TO pharm_view_owner
  USING (facility_id = app.facility_id() AND id = app.active_patient_id());

GRANT CREATE ON SCHEMA clinic TO pharm_view_owner;
SET ROLE pharm_view_owner;
CREATE VIEW clinic.pharmacist_orders_v
  WITH (security_barrier = true, security_invoker = false) AS
  SELECT o.id AS order_id,
         pt.ref AS patient_ref,
         o.drug, o.dose_value, o.dose_unit, o.frequency_per_day, o.duration_days, o.status
  FROM clinic.medication_orders o
  JOIN clinic.patients pt ON pt.id = o.patient_id
  WHERE o.facility_id = app.facility_id()
    AND o.status = 'ready_to_dispense'
    AND o.patient_id = app.active_patient_id();
REVOKE ALL ON clinic.pharmacist_orders_v FROM PUBLIC;
GRANT SELECT ON clinic.pharmacist_orders_v TO pharmacist_role;
RESET ROLE;
REVOKE CREATE ON SCHEMA clinic FROM pharm_view_owner;
