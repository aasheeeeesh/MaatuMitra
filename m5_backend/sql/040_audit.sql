-- 040_audit.sql  (run as owner_role; owner_role may SET ROLE audit_writer)
-- audit_log is append-only:
--  * app roles have NO privilege on the table; they write only through app.audit_write(),
--    a minimal SECURITY DEFINER function (pinned search_path) owned by audit_writer.
--  * who/role come from the request GUCs (set from the verified token), never from arguments.
--  * UPDATE, DELETE, TRUNCATE are revoked from everyone, and triggers raise on them as a
--    backstop (they also fire for the table owner and for superusers).

REVOKE ALL ON clinic.audit_log FROM PUBLIC;
GRANT INSERT ON clinic.audit_log TO audit_writer;
CREATE POLICY audit_writer_insert ON clinic.audit_log FOR INSERT TO audit_writer
  WITH CHECK (true);

CREATE FUNCTION app.audit_write(p_action text, p_table text, p_row uuid, p_outcome text)
  RETURNS void
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
  v_role text := current_setting('app.role', true);
BEGIN
  IF v_role IS NULL OR v_role NOT IN ('asha','nurse','physician','pharmacist','researcher','maint') THEN
    RAISE EXCEPTION 'audit_write: no valid request context';
  END IF;
  INSERT INTO clinic.audit_log (user_id, app_role, action, table_name, row_id, outcome)
  VALUES (NULLIF(current_setting('app.user_id', true), '')::uuid, v_role, p_action, p_table, p_row, p_outcome);
END
$$;
REVOKE ALL ON FUNCTION app.audit_write(text, text, uuid, text) FROM PUBLIC;
-- grant BEFORE handing ownership over (afterwards owner_role is no longer the grantor)
GRANT EXECUTE ON FUNCTION app.audit_write(text, text, uuid, text)
  TO asha_role, nurse_role, physician_role, pharmacist_role, researcher_role, maint_role;
GRANT CREATE ON SCHEMA app TO audit_writer;
ALTER FUNCTION app.audit_write(text, text, uuid, text) OWNER TO audit_writer;
REVOKE CREATE ON SCHEMA app FROM audit_writer;

CREATE FUNCTION app.audit_log_is_append_only() RETURNS trigger
  LANGUAGE plpgsql
  SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only (% refused)', TG_OP;
END
$$;
REVOKE ALL ON FUNCTION app.audit_log_is_append_only() FROM PUBLIC;

CREATE TRIGGER audit_log_no_update_delete
  BEFORE UPDATE OR DELETE ON clinic.audit_log
  FOR EACH ROW EXECUTE FUNCTION app.audit_log_is_append_only();
CREATE TRIGGER audit_log_no_truncate
  BEFORE TRUNCATE ON clinic.audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION app.audit_log_is_append_only();

-- Remove even the owner's own UPDATE/DELETE/TRUNCATE privilege (the owner could re-grant it;
-- that residual risk is why owner credentials stay with the operator only).
REVOKE UPDATE, DELETE, TRUNCATE ON clinic.audit_log FROM owner_role;
REVOKE UPDATE, DELETE, TRUNCATE ON clinic.audit_log
  FROM asha_role, nurse_role, physician_role, pharmacist_role, researcher_role, maint_role, audit_writer;
