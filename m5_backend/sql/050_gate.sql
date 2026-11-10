-- 050_gate.sql  (run as owner_role)
-- (1) Saved-record gate in the DATABASE (F1 / D-80): a record can only become 'saved' when
--     * a server-written verdict exists for the CURRENT content of the record (hash match),
--     * that verdict has at least one check, and
--     * every flag in it has a 'confirmed' resolution by the approving physician for this content.
--     The API does the richer checks (edited fields, re-verification); this trigger is the backstop
--     that also binds anyone who talks to the table directly. maint_role (operator seed loader,
--     reachable only from owner_role) is exempt so the seed can contain one finished record.
-- (2) verdicts + record_resolutions are append-only (trigger + no UPDATE/DELETE grants).
-- (3) Consent withdrawal removes the patient's research rows immediately (F4).

CREATE FUNCTION app.append_only() RETURNS trigger
  LANGUAGE plpgsql
  SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  RAISE EXCEPTION '% is append-only (% refused)', TG_TABLE_NAME, TG_OP;
END
$$;
REVOKE ALL ON FUNCTION app.append_only() FROM PUBLIC;

CREATE TRIGGER verdicts_append_only BEFORE UPDATE OR DELETE ON clinic.verdicts
  FOR EACH ROW EXECUTE FUNCTION app.append_only();
CREATE TRIGGER verdicts_no_truncate BEFORE TRUNCATE ON clinic.verdicts
  FOR EACH STATEMENT EXECUTE FUNCTION app.append_only();
CREATE TRIGGER resolutions_append_only BEFORE UPDATE OR DELETE ON clinic.record_resolutions
  FOR EACH ROW EXECUTE FUNCTION app.append_only();
CREATE TRIGGER resolutions_no_truncate BEFORE TRUNCATE ON clinic.record_resolutions
  FOR EACH STATEMENT EXECUTE FUNCTION app.append_only();
-- owner_role keeps UPDATE on verdicts only because PostgreSQL's foreign-key check
-- (SELECT ... FOR KEY SHARE from record_resolutions) needs it; the trigger above still refuses.
REVOKE DELETE, TRUNCATE ON clinic.verdicts FROM owner_role;
REVOKE UPDATE, DELETE, TRUNCATE ON clinic.record_resolutions FROM owner_role;

-- verdict.record_hash is computed here from the stored record, never supplied by the caller,
-- and the verdict must be about the record it is attached to.
CREATE FUNCTION app.verdict_bind() RETURNS trigger
  LANGUAGE plpgsql
  SET search_path = pg_catalog, pg_temp
AS $$
DECLARE r_json jsonb;
BEGIN
  SELECT json INTO r_json FROM clinic.records WHERE id = NEW.record_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'verdict: record not visible';
  END IF;
  IF NEW.verdict->>'record_id' IS DISTINCT FROM r_json->>'record_id' THEN
    RAISE EXCEPTION 'verdict: record_id does not match the stored record';
  END IF;
  NEW.record_hash := app.record_hash(r_json);
  RETURN NEW;
END
$$;
REVOKE ALL ON FUNCTION app.verdict_bind() FROM PUBLIC;
CREATE TRIGGER verdicts_bind BEFORE INSERT ON clinic.verdicts
  FOR EACH ROW EXECUTE FUNCTION app.verdict_bind();

CREATE FUNCTION app.records_saved_gate() RETURNS trigger
  LANGUAGE plpgsql
  SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
  v_hash text := app.record_hash(NEW.json);
  v_checks jsonb;
  v_unresolved int;
BEGIN
  IF NEW.status <> 'saved' OR (TG_OP = 'UPDATE' AND OLD.status = 'saved') OR current_user = 'maint_role' THEN
    RETURN NEW;
  END IF;
  SELECT v.verdict->'checks' INTO v_checks
    FROM clinic.verdicts v
    WHERE v.record_id = NEW.id AND v.record_hash = v_hash
    ORDER BY v.created_at DESC, v.id DESC LIMIT 1;
  IF v_checks IS NULL OR jsonb_array_length(v_checks) = 0 THEN
    RAISE EXCEPTION 'saved gate: no server-written verdict for the current record content'
      USING ERRCODE = 'check_violation';
  END IF;
  SELECT count(*) INTO v_unresolved
  FROM (SELECT DISTINCT c->>'check_id' AS check_id, c->>'field_path' AS field_path
        FROM jsonb_array_elements(v_checks) c WHERE c->>'status' = 'flag') f
  WHERE NOT EXISTS (
    SELECT 1 FROM clinic.record_resolutions x
    WHERE x.record_id = NEW.id AND x.record_hash = v_hash AND x.resolved_by = NEW.approved_by
      AND x.action = 'confirmed' AND x.check_id = f.check_id AND x.field_path = f.field_path);
  IF v_unresolved > 0 THEN
    RAISE EXCEPTION 'saved gate: % unresolved verdict flag(s)', v_unresolved
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END
$$;
REVOKE ALL ON FUNCTION app.records_saved_gate() FROM PUBLIC;
CREATE TRIGGER records_saved_gate BEFORE INSERT OR UPDATE ON clinic.records
  FOR EACH ROW EXECUTE FUNCTION app.records_saved_gate();

-- F4: withdrawing (or deleting) a consent deletes that patient's research rows in the same
-- transaction. The map table lets us find the pseudonym without storing the HMAC key here.
CREATE FUNCTION app.consent_withdrawn() RETURNS trigger
  LANGUAGE plpgsql
  SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  DELETE FROM research.encounters_deid
   WHERE pseudonym IN (SELECT pseudonym FROM research.pseudonym_map WHERE patient_id = OLD.patient_id);
  DELETE FROM research.pseudonym_map WHERE patient_id = OLD.patient_id;
  RETURN NULL;
END
$$;
REVOKE ALL ON FUNCTION app.consent_withdrawn() FROM PUBLIC;
CREATE TRIGGER consents_withdrawn AFTER UPDATE ON clinic.consents
  FOR EACH ROW WHEN (OLD.research_ok AND NOT NEW.research_ok)
  EXECUTE FUNCTION app.consent_withdrawn();
CREATE TRIGGER consents_deleted AFTER DELETE ON clinic.consents
  FOR EACH ROW EXECUTE FUNCTION app.consent_withdrawn();
