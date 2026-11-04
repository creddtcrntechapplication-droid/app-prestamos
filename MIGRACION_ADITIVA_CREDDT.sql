-- Adiciones idempotentes; no modifica pagos ni contratos históricos.
BEGIN;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;

CREATE SCHEMA IF NOT EXISTS creddt_private;
REVOKE ALL ON SCHEMA creddt_private FROM PUBLIC;
CREATE TABLE IF NOT EXISTS creddt_private.device_sessions (
 token_hash TEXT PRIMARY KEY,
 usuario TEXT NOT NULL,
 credential_stamp TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 expires_at TIMESTAMPTZ NOT NULL,
 revoked BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS creddt_device_user ON creddt_private.device_sessions(usuario);
ALTER TABLE creddt_private.device_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON creddt_private.device_sessions FROM PUBLIC;
CREATE TABLE IF NOT EXISTS creddt_private.login_attempts (
 identity_hash TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0,
 window_start TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE creddt_private.login_attempts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON creddt_private.login_attempts FROM PUBLIC;
DO $$ BEGIN
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN
  REVOKE ALL ON SCHEMA creddt_private FROM anon;
  REVOKE ALL ON ALL TABLES IN SCHEMA creddt_private FROM anon;
 END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN
  REVOKE ALL ON SCHEMA creddt_private FROM authenticated;
  REVOKE ALL ON ALL TABLES IN SCHEMA creddt_private FROM authenticated;
 END IF;
END $$;


CREATE SCHEMA IF NOT EXISTS creddt_private;
REVOKE ALL ON SCHEMA creddt_private FROM PUBLIC;
CREATE TABLE IF NOT EXISTS creddt_private.installment_ledger (
 id_cuota BIGINT PRIMARY KEY,
 prestamo_id TEXT NOT NULL,
 version TEXT NOT NULL,
 capital_pendiente NUMERIC(20,2) NOT NULL CHECK(capital_pendiente >= 0),
 interes_pendiente NUMERIC(20,2) NOT NULL CHECK(interes_pendiente >= 0)
);
CREATE INDEX IF NOT EXISTS creddt_ledger_loan ON creddt_private.installment_ledger(prestamo_id);
ALTER TABLE creddt_private.installment_ledger ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON creddt_private.installment_ledger FROM PUBLIC;
DO $$ BEGIN
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN
  REVOKE ALL ON creddt_private.installment_ledger FROM anon;
 END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN
  REVOKE ALL ON creddt_private.installment_ledger FROM authenticated;
 END IF;
END $$;

COMMIT;
