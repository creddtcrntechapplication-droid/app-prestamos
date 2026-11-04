"""Sesiones revocables validadas en PostgreSQL. Nunca persiste contraseñas en el navegador."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from sqlalchemy import text

SCHEMA_SQL = """
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
"""

def digest(token):
    return hashlib.sha256(str(token).encode()).hexdigest()

def credential_stamp(user):
    return digest(str(user['password_hash'])+'|'+str(user['password_salt']))

def current_user(conn, username):
    row=conn.execute(text('SELECT usuario,rol,password_hash,password_salt,activo FROM usuarios WHERE usuario=:u'),{'u':username}).mappings().first()
    return dict(row) if row and row['activo'] and row['rol'] in ('ADMIN','ASESOR','CONSULTA') else None

def issue(conn,user,days=7):
    days=int(days)
    if not 1<=days<=30:raise ValueError('La duración debe estar entre 1 y 30 días.')
    token=secrets.token_urlsafe(32);expires=datetime.now(timezone.utc)+timedelta(days=days)
    conn.execute(text('INSERT INTO creddt_private.device_sessions(token_hash,usuario,credential_stamp,expires_at) VALUES(:t,:u,:s,:e)'),
                 {'t':digest(token),'u':user['usuario'],'s':credential_stamp(user),'e':expires})
    return token,expires.timestamp()

def restore(conn,token):
    if not isinstance(token,str) or len(token)!=43 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in token):return None
    row=conn.execute(text('''SELECT s.usuario,s.credential_stamp,s.expires_at FROM creddt_private.device_sessions s
      WHERE s.token_hash=:t AND NOT s.revoked AND s.expires_at>now()'''),{'t':digest(token)}).mappings().first()
    if not row:return None
    user=current_user(conn,row['usuario'])
    if not user or credential_stamp(user)!=row['credential_stamp']:return None
    user['expires_at']=row['expires_at'].timestamp()
    return user

def revoke(conn,token):
    conn.execute(text('UPDATE creddt_private.device_sessions SET revoked=TRUE WHERE token_hash=:t'),{'t':digest(token)})

def revoke_user(conn,username):
    conn.execute(text('UPDATE creddt_private.device_sessions SET revoked=TRUE WHERE usuario=:u'),{'u':username})

def login_allowed(conn,username):
    row=conn.execute(text('SELECT failures,window_start FROM creddt_private.login_attempts WHERE identity_hash=:u'),{'u':digest(username)}).mappings().first()
    return not row or row['failures']<10 or row['window_start']<datetime.now(timezone.utc)-timedelta(minutes=15)

def login_failure(conn,username):
    conn.execute(text('''INSERT INTO creddt_private.login_attempts(identity_hash,failures) VALUES(:u,1)
      ON CONFLICT(identity_hash) DO UPDATE SET
      failures=CASE WHEN creddt_private.login_attempts.window_start<now()-interval '15 minutes' THEN 1 ELSE creddt_private.login_attempts.failures+1 END,
      window_start=CASE WHEN creddt_private.login_attempts.window_start<now()-interval '15 minutes' THEN now() ELSE creddt_private.login_attempts.window_start END'''),{'u':digest(username)})

def login_success(conn,username):
    conn.execute(text('DELETE FROM creddt_private.login_attempts WHERE identity_hash=:u'),{'u':digest(username)})
