import streamlit as st
import pandas as pd
import os
from streamlit.errors import StreamlitSecretNotFoundError
import tempfile
import base64
import requests
import math
import time
import uuid
from decimal import Decimal
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine, text
from reportlab.lib import pagesizes, colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    HRFlowable,
)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
# ==========================
# CONFIGURACIÓN
# ==========================
st.set_page_config(page_title="CREDDT | CRNTECH", layout="wide")
# ==========================
# CONEXIÓN A SUPABASE
# ==========================
def get_config(key, default=""):
    value = os.getenv(key)
    if value not in (None, ""):
        return value
    try:
        return st.secrets.get(key, default)
    except StreamlitSecretNotFoundError:
        return default

DATABASE_URL = get_config("DATABASE_URL")
try:
    # Creamos el motor de conexión usando el puerto 6543 y SSL
    engine = create_engine(
        DATABASE_URL,
        connect_args={"sslmode": "require"},
        pool_pre_ping=True # Esto ayuda a que si la conexión se duerme, se despierte sola
    )
except Exception as e:
    st.error(f"❌ Error al conectar con la base de datos: {e}")
    st.stop()
# ==========================
# FUNCIONES DE UTILIDAD
# ==========================
def get_conn():
    """Devuelve una conexión activa a la base de datos"""
    return engine.connect()
def ejecutar_sql(query, params=None, fetch=False):
    """
    Ejecuta una consulta SQL.
    - query: string con SQL
    - params: diccionario o lista de parámetros
    - fetch: si True, retorna todos los resultados
    """
    params = params or {}
    with get_conn() as conn:
        result = conn.execute(text(query), params)
        if fetch:
            return result.fetchall()
        return result

# ==========================
# 🔐 USUARIO ADMIN
# ==========================
def init_usuario_admin():
    with get_conn() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                usuario TEXT UNIQUE,
                password TEXT,
                rol TEXT
            )
        """))
        # Insertar admin si no existe
        conn.execute(text("""
            INSERT INTO usuarios (usuario, password, rol)
            VALUES ('admin', 'Sandra*123', 'ADMIN')
            ON CONFLICT (usuario) DO NOTHING
        """))
 
        conn.commit()
  
init_usuario_admin()
# ==========================
# 🔐 ACCESO OBLIGATORIO
# ==========================
raw_token_aceptar = st.query_params.get("aceptar", None)
if isinstance(raw_token_aceptar, list):
    token_aceptar = raw_token_aceptar[0] if raw_token_aceptar else None
else:
    token_aceptar = raw_token_aceptar
if "auth" not in st.session_state:
    st.session_state.auth = False
    st.session_state.usuario = None
    st.session_state.rol = None
if not st.session_state.auth and not token_aceptar:
    st.markdown("""
    <style>
    .block-container{
        padding-top: 0.25rem !important;
        padding-bottom: 1rem !important;
        max-width: 100% !important;
    }
    .login-shell{
        max-width: 860px;
        margin: 0 auto;
        padding: 0.15rem 0 1rem 0;
    }
    .login-stage{
        position: relative;
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        border: 1px solid #e2e8f0;
        border-radius: 30px;
        overflow: hidden;
        box-shadow: 0 26px 70px rgba(15,23,42,.10);
    }
    .login-stage::before{
        content: "";
        position: absolute;
        inset: 0;
        background: radial-gradient(circle at top right, rgba(37,99,235,.08), transparent 30%);
        pointer-events: none;
    }
    .login-head{
        padding: 20px 28px 14px 28px;
        background:#ffffff;
        position: relative;
        z-index: 1;
    }
    .login-title-wrap{
        text-align:center;
        padding-right: 46px;
        padding-top: 8px;
    }
    .login-title-wrap h1{
        margin:0;
        font-size:50px;
        line-height:1.02;
        font-weight:900;
        letter-spacing:-.035em;
        color:#0f172a;
    }
    .login-title-wrap p{
        margin:10px 0 0 0;
        font-size:20px;
        line-height:1.55;
        color:#64748b;
        font-weight:500;
    }
    .login-blue-bar{
        height: 5px;
        background: linear-gradient(90deg, #081a44 0%, #173266 48%, #2563eb 100%);
        position: relative;
        z-index: 1;
    }
    .login-body{
        padding: 24px 30px 24px 30px;
        position: relative;
        z-index: 1;
    }
    .login-kicker{
        display:inline-block;
        font-size:12px;
        font-weight:800;
        letter-spacing:.16em;
        color:#2563eb;
        background:#eff6ff;
        border:1px solid #dbeafe;
        border-radius:999px;
        padding:8px 13px;
        margin-bottom:16px;
        text-transform: uppercase;
    }
    .login-title{
        font-size:44px;
        line-height:1.04;
        font-weight:900;
        color:#0f172a;
        margin:0 0 12px 0;
        letter-spacing:-.035em;
    }
    .login-sub{
        font-size:17px;
        line-height:1.72;
        color:#64748b;
        margin:0 0 16px 0;
    }
    .login-note{
        text-align:center;
        color:#94a3b8;
        font-size:12.5px;
        margin-top:16px;
    }
    div[data-testid="stForm"]{
        border: 1px solid #dfe7f2 !important;
        border-radius: 22px !important;
        padding: 18px 18px 16px 18px !important;
        background: rgba(255,255,255,.94) !important;
        box-shadow: 0 12px 30px rgba(15,23,42,.06) !important;
        backdrop-filter: blur(6px);
        margin-top: 0 !important;
    }
    div[data-testid="stForm"] > div{
        border: 0 !important;
        padding: 0 !important;
        background: transparent !important;
    }
    .stTextInput > div > div > input{
        border-radius: 14px !important;
        border:1px solid #dbe3ef !important;
        background:#f8fafc !important;
        min-height: 52px !important;
        font-size:16px !important;
        padding-left: 14px !important;
    }
    .stTextInput > label{
        font-weight:700 !important;
        color:#334155 !important;
    }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button{
        border-radius: 14px !important;
        min-height: 54px !important;
        font-size: 17px !important;
        font-weight: 800 !important;
        border: 0 !important;
        background: linear-gradient(135deg, #0b1633 0%, #173266 42%, #2563eb 100%) !important;
        box-shadow: 0 12px 24px rgba(37,99,235,.20) !important;
        transition: all .18s ease !important;
    }
    div.stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover{
        transform: translateY(-1px);
        box-shadow: 0 16px 30px rgba(37,99,235,.24) !important;
    }
    @media (max-width: 768px){
        .login-shell{max-width: 100%;}
        .login-head{padding:16px 18px 14px 18px;}
        .login-body{padding:18px;}
        .login-title-wrap{padding-right:0;padding-top:0;text-align:left;}
        .login-title-wrap h1{font-size:36px;}
        .login-title-wrap p{font-size:16px;}
        .login-title{font-size:32px;}
        .login-sub{font-size:15px;}
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='login-shell'><div class='login-stage'>", unsafe_allow_html=True)

    st.markdown("<div class='login-head'>", unsafe_allow_html=True)
    logo_col, title_col = st.columns([1.0, 4.5], gap="small")
    with logo_col:
        st.image("logo_creddt.png", width=132)
    with title_col:
        st.markdown(
            "<div class='login-title-wrap'><h1>CREDDT | CRNTECH</h1><p>Plataforma inteligente de gestión de créditos</p></div>",
            unsafe_allow_html=True
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='login-blue-bar'></div>", unsafe_allow_html=True)
    st.markdown("<div class='login-body'>", unsafe_allow_html=True)
    st.markdown("<div class='login-kicker'>Acceso seguro</div>", unsafe_allow_html=True)
    st.markdown("<div class='login-title'>Bienvenido al sistema</div>", unsafe_allow_html=True)
    st.markdown("<div class='login-sub'>Ingresa tus credenciales para administrar clientes, créditos, pagos y seguimiento operativo desde un solo panel.</div>", unsafe_allow_html=True)
    with st.form("login_form", clear_on_submit=False):
        usuario = st.text_input("Usuario", placeholder="Ingresa tu usuario")
        clave = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
        ingresar = st.form_submit_button("Ingresar", use_container_width=True, type="primary")

    if ingresar:
        with get_conn() as conn:
            user = conn.execute(
                text("""
                    SELECT usuario, rol 
                    FROM usuarios 
                    WHERE usuario=:usuario AND password=:password
                """),
                {"usuario": usuario, "password": clave}
            ).fetchone()
        if user:
            st.session_state.auth = True
            st.session_state.usuario = user[0]
            st.session_state.rol = user[1]
            st.rerun()
        else:
            st.error("❌ Usuario o contraseña incorrectos")

    st.markdown("<div class='login-note'>Acceso privado • Plataforma de operación interna</div>", unsafe_allow_html=True)
    st.markdown("</div></div></div>", unsafe_allow_html=True)
    st.stop()
# ==========================
# ROLES Y PERMISOS
# ==========================
ROL_ACTUAL = str(st.session_state.get("rol") or "CONSULTA").upper()

def tiene_rol(*roles):
    return ROL_ACTUAL in {r.upper() for r in roles}

ES_ADMIN = tiene_rol("ADMIN")
ES_ASESOR = tiene_rol("ASESOR")
ES_CONSULTA = tiene_rol("CONSULTA")

PUEDE_VER_CLIENTES = tiene_rol("ADMIN", "ASESOR", "CONSULTA")
PUEDE_REGISTRAR_CLIENTES = tiene_rol("ADMIN", "ASESOR")
PUEDE_GESTIONAR_CLIENTES = tiene_rol("ADMIN", "ASESOR")
PUEDE_BORRAR_CLIENTES = tiene_rol("ADMIN")
PUEDE_CREAR_CREDITOS = tiene_rol("ADMIN", "ASESOR")
PUEDE_VER_CONTRATOS_PENDIENTES = tiene_rol("ADMIN", "ASESOR")
PUEDE_VER_DETALLE = tiene_rol("ADMIN", "ASESOR", "CONSULTA")
PUEDE_REGISTRAR_PAGOS = tiene_rol("ADMIN", "ASESOR")
PUEDE_USAR_SIMULADOR = tiene_rol("ADMIN", "ASESOR", "CONSULTA")

# ==========================
# HEADER - TITULO
# ==========================
st.markdown("""
<style>
.app-header{
    background: #ffffff;
    border-radius: 22px;
    padding: 12px 6px 6px 6px;
    margin: 0.15rem 0 0.55rem 0;
}
.app-title-wrap{
    text-align:center;
    padding-top:8px;
}
.app-title{
    margin:0;
    color:#0f172a;
    font-size:42px;
    line-height:1.04;
    font-weight:900;
    letter-spacing:-.03em;
}
.app-subtitle{
    color:#64748b;
    margin-top:6px;
    font-size:16px;
    font-weight:500;
}
.app-chip{
    display:inline-block;
    background:#eff6ff;
    color:#1d4ed8;
    border:1px solid #dbeafe;
    border-radius:999px;
    padding:7px 12px;
    font-size:12px;
    font-weight:700;
    margin-left:8px;
    margin-top:6px;
}
.app-main-line{
    height: 6px;
    width: 100%;
    border-radius: 999px;
    margin: 12px 0 8px 0;
    background: linear-gradient(90deg, #081a44 0%, #1d4ed8 55%, #081a44 100%);
    box-shadow: 0 8px 18px rgba(29,78,216,.14);
}
.section-divider{
    margin: 16px 0 14px 0;
}
.section-divider.compact{
    margin: 8px 0 10px 0;
}
.section-divider-line{
    position: relative;
    width: 100%;
    height: 2px;
    border-radius: 999px;
    background: #e5edf7;
    border: 0;
    overflow: hidden;
}
.section-divider-line::before{
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #081a44 0%, #1d4ed8 100%);
}
@media (max-width: 900px){
    .app-title{font-size:34px;}
    .app-subtitle{font-size:15px;}
}
</style>
""", unsafe_allow_html=True)

def render_section_divider(variant="default"):
    css_class = "section-divider compact" if variant == "compact" else "section-divider"
    st.markdown(
        f"<div class='{css_class}'><div class='section-divider-line'></div></div>",
        unsafe_allow_html=True
    )

usuario_hdr = st.session_state.get("usuario", "-")
rol_hdr = st.session_state.get("rol", "-")

st.markdown("<div class='app-header'>", unsafe_allow_html=True)
col_logo, col_centro, col_derecha = st.columns([1.0, 4.8, 2.0], gap="small")
with col_logo:
    st.image("logo_creddt.png", width=98)
with col_centro:
    st.markdown(
        "<div class='app-title-wrap'><div class='app-title'>CREDDT | CRNTECH</div><div class='app-subtitle'>Plataforma inteligente de gestión de créditos</div></div>",
        unsafe_allow_html=True
    )
with col_derecha:
    st.markdown(
        f"<div style='text-align:right;padding-top:10px;'><span class='app-chip'>Usuario: <strong>{usuario_hdr}</strong></span><br><span class='app-chip'>Rol: <strong>{rol_hdr}</strong></span></div>",
        unsafe_allow_html=True
    )
st.markdown("<div class='app-main-line'></div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.get("app_busy") and st.session_state.get("app_busy_label"):
    st.info(f"⏳ {st.session_state.get('app_busy_label')}")
st.markdown("""
<style>
@media (max-width: 1024px) {
  div[data-testid="stHorizontalBlock"] {
    gap: .75rem !important;
    flex-wrap: wrap !important;
  }
}
@media (max-width: 768px) {
  div[data-testid="column"] {
    width: 100% !important;
    flex: 1 1 100% !important;
    min-width: 100% !important;
  }
  div.stButton > button, button[kind] {
    width: 100% !important;
  }
  div[data-testid="stMetric"] {
    min-width: 100% !important;
  }
  div[data-testid="stTabs"] button {
    font-size: .85rem !important;
    padding: .45rem .7rem !important;
  }
}
</style>
""", unsafe_allow_html=True)
# ==========================
# VARIABLES SEGURAS
# ==========================
BREVO_API_KEY = get_config("BREVO_API_KEY")
BREVO_FROM_EMAIL = get_config("BREVO_FROM_EMAIL")
BREVO_FROM_NAME = get_config("BREVO_FROM_NAME", "CREDDT CRNTECH APPLICATION")
APP_BASE_URL = get_config("APP_BASE_URL").rstrip("/")
def asegurar_estructura_base():
    with get_conn() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS clientes (
                cedula TEXT PRIMARY KEY,
                nombres TEXT,
                apellidos TEXT,
                ciudad TEXT,
                telefono TEXT,
                correo TEXT,
                direccion TEXT,
                empresa TEXT,
                fecha_nacimiento TEXT,
                cargo TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS prestamos (
                id TEXT PRIMARY KEY,
                cliente_cedula TEXT,
                monto_original NUMERIC(18,2),
                cuotas INTEGER,
                frecuencia TEXT,
                valor_cuota NUMERIC(18,2),
                estado TEXT,
                tipo TEXT DEFAULT 'Normal',
                saldo_capital NUMERIC(18,2),
                tasa_mensual NUMERIC(12,6),
                contrato_aceptado INTEGER DEFAULT 0,
                contrato_token TEXT,
                fecha_aceptacion TEXT,
                fecha_desembolso TEXT,
                contrato_enviado INTEGER DEFAULT 0,
                fecha_envio_contrato TEXT,
                desembolso_notificado INTEGER DEFAULT 0,
                fecha_inicio TEXT,
                FOREIGN KEY(cliente_cedula) REFERENCES clientes(cedula)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cuotas (
                id_cuota SERIAL PRIMARY KEY,
                prestamo_id TEXT,
                nro_cuota INTEGER,
                fecha_vencimiento TEXT,
                valor_cuota NUMERIC(18,2),
                estado TEXT,
                FOREIGN KEY(prestamo_id) REFERENCES prestamos(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pagos (
                id_pago SERIAL PRIMARY KEY,
                prestamo_id TEXT,
                fecha_pago TEXT,
                valor NUMERIC(18,2),
                estado TEXT,
                tipo_movimiento TEXT,
                detalle TEXT,
                FOREIGN KEY(prestamo_id) REFERENCES prestamos(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pagos_cuotas (
                id_pago INTEGER,
                id_cuota INTEGER,
                valor_aplicado NUMERIC(18,2),
                FOREIGN KEY(id_pago) REFERENCES pagos(id_pago),
                FOREIGN KEY(id_cuota) REFERENCES cuotas(id_cuota)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS reminders_sent (
                id SERIAL PRIMARY KEY,
                id_cuota INTEGER,
                tipo_recordatorio TEXT,
                fecha_envio TEXT
            )
        """))
        for s in [
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS frecuencia TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS contrato_aceptado INTEGER DEFAULT 0",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS contrato_token TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_aceptacion TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_desembolso TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS contrato_enviado INTEGER DEFAULT 0",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_envio_contrato TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS desembolso_notificado INTEGER DEFAULT 0",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_inicio TEXT",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS tipo_movimiento TEXT",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS detalle TEXT",
            "ALTER TABLE pagos_cuotas ADD COLUMN IF NOT EXISTS valor_aplicado NUMERIC(18,2)",
            "ALTER TABLE reminders_sent ADD COLUMN IF NOT EXISTS tipo_recordatorio TEXT"
        ]:
            conn.execute(text(s))
        conn.execute(text("""
            UPDATE prestamos
            SET saldo_capital = COALESCE(saldo_capital, monto_original),
                tasa_mensual = COALESCE(tasa_mensual, 0),
                contrato_aceptado = COALESCE(contrato_aceptado, 0),
                contrato_enviado = COALESCE(contrato_enviado, 0),
                desembolso_notificado = COALESCE(desembolso_notificado, 0),
                fecha_inicio = COALESCE(fecha_inicio, CURRENT_DATE::text),
                frecuencia = COALESCE(frecuencia, 'Mensual')
            WHERE saldo_capital IS NULL
               OR tasa_mensual IS NULL
               OR contrato_aceptado IS NULL
               OR contrato_enviado IS NULL
               OR desembolso_notificado IS NULL
               OR fecha_inicio IS NULL
               OR frecuencia IS NULL
        """))
        conn.commit()
asegurar_estructura_base()
def asegurar_estructura_financiera():
    with get_conn() as conn:
        sentencias = [
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS saldo_capital NUMERIC(18,2)",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS tasa_mensual NUMERIC(12,6)",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS tipo_movimiento TEXT",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS detalle TEXT",
            "ALTER TABLE pagos_cuotas ADD COLUMN IF NOT EXISTS valor_aplicado NUMERIC(18,2)"
        ]
        for sentencia in sentencias:
            conn.execute(text(sentencia))
        conn.execute(text("""
            UPDATE prestamos
            SET saldo_capital = COALESCE(saldo_capital, monto_original),
                tasa_mensual = COALESCE(tasa_mensual, 0)
            WHERE saldo_capital IS NULL OR tasa_mensual IS NULL
        """))
        conn.commit()
asegurar_estructura_financiera()

# ==========================
# MENSAJES DE CONFIRMACIÓN
# ==========================
def set_flash(key, tipo, texto):
    st.session_state[key] = {"tipo": tipo, "texto": texto}

def show_flash(key):
    msg = st.session_state.get(key)
    if not msg:
        return
    tipo = msg.get("tipo", "success")
    texto = msg.get("texto", "")
    if tipo == "success":
        st.success(texto)
    elif tipo == "error":
        st.error(texto)
    elif tipo == "warning":
        st.warning(texto)
    else:
        st.info(texto)
    st.session_state[key] = None

for _flash_key in ["clientes_msg", "credito_msg", "detalle_msg", "contrato_msg", "recordatorios_msg", "sistema_msg"]:
    if _flash_key not in st.session_state:
        st.session_state[_flash_key] = None

if "app_busy" not in st.session_state:
    st.session_state.app_busy = False
if "app_busy_label" not in st.session_state:
    st.session_state.app_busy_label = None

def start_busy(label="Procesando..."):
    st.session_state.app_busy = True
    st.session_state.app_busy_label = label

def stop_busy():
    st.session_state.app_busy = False
    st.session_state.app_busy_label = None
# ==========================
# UTILIDADES
# ==========================
def pesos(valor):
    try:
        return f"${float(valor):,.0f}".replace(",", ".")
    except Exception:
        return "$0"
def normalizar_decimal(valor):
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))
def enviar_correo(destino, asunto, cuerpo):
    ok, error = enviar_correo_mailersend(
        destino=destino,
        asunto=asunto,
        cuerpo=cuerpo
    )
    if not ok:
        st.warning(f"⚠️ El correo no pudo enviarse: {error}")
def calcular_cuota_amortizada(capital, tasa_mensual, cuotas_restantes):
    capital = float(capital or 0)
    tasa_mensual = float(tasa_mensual or 0)
    cuotas_restantes = int(cuotas_restantes or 0)
    if capital <= 0 or cuotas_restantes <= 0:
        return 0.0
    if tasa_mensual <= 0:
        return round(capital / cuotas_restantes, 2)
    factor = (1 + tasa_mensual) ** cuotas_restantes
    cuota = capital * ((tasa_mensual * factor) / (factor - 1))
    return round(cuota, 2)
def obtener_proxima_cuota(conn, prestamo_id):
    return conn.execute(text("""
        SELECT id_cuota, nro_cuota, valor_cuota, fecha_vencimiento, estado
        FROM cuotas
        WHERE prestamo_id = :id
          AND estado <> 'Pagada'
        ORDER BY nro_cuota ASC
        LIMIT 1
    """), {"id": prestamo_id}).fetchone()

def _area_responsable(tipo_correo):
    return {
        "CONTRATO": "Área de Aprobación",
        "DESEMBOLSO": "Área de Operaciones",
        "RECORDATORIO": "Área de Cartera",
        "RECIBO_CUOTA": "Área Administrativa y Financiera",
        "RECIBO_ABONO": "Área Administrativa y Financiera",
    }.get(tipo_correo, "Área Administrativa y Financiera")


def _titulo_correo(tipo_correo):
    return {
        "CONTRATO": "Aceptación de contrato de crédito",
        "DESEMBOLSO": "Confirmación de activación y desembolso",
        "RECORDATORIO": "Recordatorio de pago",
        "RECIBO_CUOTA": "Confirmación de pago recibido",
        "RECIBO_ABONO": "Confirmación de abono a capital",
    }.get(tipo_correo, "Notificación de crédito")


def _intro_correo(tipo_correo):
    return {
        "CONTRATO": "Adjuntamos el contrato de su crédito para revisión y aceptación. Este documento contiene el resumen aprobado de la operación y sus condiciones generales.",
        "DESEMBOLSO": "Le confirmamos que su contrato fue aceptado correctamente y que su crédito quedó activo para continuar el proceso operativo del desembolso.",
        "RECORDATORIO": "Le recordamos oportunamente la información de su obligación para facilitar la gestión de pago y mantener su crédito al día.",
        "RECIBO_CUOTA": "Le confirmamos que el pago de su cuota fue registrado exitosamente en nuestro sistema. Adjuntamos el comprobante para su soporte.",
        "RECIBO_ABONO": "Le confirmamos que su abono a capital fue registrado exitosamente en nuestro sistema. Adjuntamos el comprobante para su soporte.",
    }.get(tipo_correo, "Adjuntamos la información correspondiente a su crédito para consulta y soporte.")


def _resumen_items_correo(tipo_correo, **kwargs):
    if tipo_correo == "CONTRATO":
        return [
            ("Crédito", kwargs.get("prestamo_id")),
            ("Monto aprobado", pesos(kwargs.get("monto"))),
            ("Número de cuotas", kwargs.get("cuotas")),
            ("Valor de la cuota", pesos(kwargs.get("valor_cuota"))),
            ("Tipo de crédito", kwargs.get("tipo_credito") or kwargs.get("tipo")),
        ]
    if tipo_correo == "DESEMBOLSO":
        return [
            ("Crédito", kwargs.get("prestamo_id")),
            ("Tipo de crédito", kwargs.get("tipo_credito") or kwargs.get("tipo")),
            ("Monto aprobado", pesos(kwargs.get("monto"))),
            ("Frecuencia", kwargs.get("frecuencia")),
            ("Número de cuotas", kwargs.get("cuotas")),
            ("Valor de la cuota", pesos(kwargs.get("valor_cuota"))),
        ]
    if tipo_correo == "RECORDATORIO":
        return [
            ("Crédito", kwargs.get("prestamo_id")),
            ("Cuota", kwargs.get("cuota_nro")),
            ("Fecha de vencimiento", kwargs.get("fecha_vencimiento")),
            ("Valor a pagar", pesos(kwargs.get("valor"))),
        ]
    if tipo_correo == "RECIBO_CUOTA":
        return [
            ("Crédito", kwargs.get("prestamo_id")),
            ("Cuota aplicada", kwargs.get("cuota_nro")),
            ("Fecha de pago", kwargs.get("fecha_pago")),
            ("Valor pagado", pesos(kwargs.get("valor"))),
        ]
    if tipo_correo == "RECIBO_ABONO":
        return [
            ("Crédito", kwargs.get("prestamo_id")),
            ("Fecha del abono", kwargs.get("fecha_pago")),
            ("Abono a capital", pesos(kwargs.get("valor"))),
            ("Nuevo saldo capital", pesos(kwargs.get("saldo_capital"))),
            ("Nueva cuota estimada", pesos(kwargs.get("nueva_cuota"))),
        ]
    return []


def construir_cuerpo_correo(tipo_correo, nombre_cliente, **kwargs):
    area = _area_responsable(tipo_correo)
    titulo = _titulo_correo(tipo_correo)
    intro = _intro_correo(tipo_correo)
    lineas = [
        f"Estimado(a) {nombre_cliente},",
        "",
        "Reciba un cordial saludo de CREDDT CRNTECH.",
        "",
        intro,
        "",
        f"{titulo}:",
    ]
    for etiqueta, valor in _resumen_items_correo(tipo_correo, **kwargs):
        if valor not in (None, ""):
            lineas.append(f"- {etiqueta}: {valor}")
    if tipo_correo == "CONTRATO" and kwargs.get("link_aceptacion"):
        lineas.extend([
            "",
            "Para continuar con el proceso, por favor confirme la aceptación del contrato desde el enlace incluido en el correo.",
        ])
    elif tipo_correo == "RECORDATORIO":
        lineas.extend([
            "",
            "Agradecemos realizar el pago dentro del plazo correspondiente para mantener su obligación al día.",
        ])
    lineas.extend([
        "",
        "Cordialmente,",
        "CREDDT CRNTECH",
        area,
    ])
    return "\n".join(lineas)


def construir_html_correo(tipo_correo, nombre_cliente, **kwargs):
    titulo = _titulo_correo(tipo_correo)
    area = _area_responsable(tipo_correo)
    intro = _intro_correo(tipo_correo)
    filas = _resumen_items_correo(tipo_correo, **kwargs)
    filas_html = "".join(
        f"""
        <tr>
            <td style=\"padding:10px 0;font-size:14px;color:#64748b;border-bottom:1px solid #e5e7eb;\">{label}</td>
            <td align=\"right\" style=\"padding:10px 0;font-size:14px;font-weight:700;color:#0f172a;border-bottom:1px solid #e5e7eb;\">{value if value not in (None, '') else '-'}</td>
        </tr>
        """
        for label, value in filas
    )
    bloque_accion = ""
    if tipo_correo == "CONTRATO" and kwargs.get("link_aceptacion"):
        enlace = kwargs.get("link_aceptacion")
        bloque_accion = f"""
        <div style=\"text-align:center;margin:28px 0 20px 0;\">
            <a href=\"{enlace}\" target=\"_blank\" style=\"display:inline-block;background:#0f172a;color:#ffffff;text-decoration:none;padding:14px 28px;border-radius:10px;font-weight:700;\">Aceptar contrato</a>
        </div>
        <p style=\"margin:0;font-size:12px;line-height:1.7;color:#64748b;word-break:break-all;\">
            Si el botón no abre correctamente, copie y pegue este enlace en su navegador:<br>
            <a href=\"{enlace}\" target=\"_blank\" style=\"color:#2563eb;text-decoration:none;\">{enlace}</a>
        </p>
        """

    return f"""
    <div style=\"margin:0;padding:24px;background:#f3f6fb;font-family:Arial,Helvetica,sans-serif;color:#0f172a;\">
        <div style=\"max-width:720px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;overflow:hidden;\">
            <div style=\"background:#0f172a;padding:28px 32px;\">
                <div style=\"font-size:24px;font-weight:800;color:#ffffff;letter-spacing:.2px;\">CREDDT CRNTECH</div>
                <div style=\"margin-top:6px;font-size:14px;color:#cbd5e1;\">{titulo}</div>
            </div>
            <div style=\"padding:30px 32px;\">
                <p style=\"margin:0 0 16px 0;font-size:15px;line-height:1.75;\">Estimado(a) <strong>{nombre_cliente}</strong>,</p>
                <p style=\"margin:0 0 18px 0;font-size:15px;line-height:1.75;color:#334155;\">{intro}</p>
                <div style=\"background:#f8fafc;border:1px solid #e5e7eb;border-radius:14px;padding:20px 22px;margin:0 0 24px 0;\">
                    <div style=\"font-size:13px;font-weight:700;letter-spacing:.4px;color:#475569;margin-bottom:12px;text-transform:uppercase;\">Resumen de la operación</div>
                    <table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"border-collapse:collapse;\">{filas_html}</table>
                </div>
                {bloque_accion}
                <div style=\"border-top:1px solid #e5e7eb;padding-top:18px;margin-top:18px;\">
                    <p style=\"margin:0;font-size:14px;line-height:1.7;color:#334155;\">Cordialmente,<br><strong>CREDDT CRNTECH</strong><br>{area}</p>
                </div>
            </div>
            <div style=\"background:#f8fafc;border-top:1px solid #e5e7eb;padding:16px 32px;font-size:12px;line-height:1.6;color:#64748b;\">
                Este mensaje fue generado automáticamente por CREDDT CRNTECH. Si requiere validación adicional, responda este correo o contacte el área responsable.
            </div>
        </div>
    </div>
    """


def generar_recibo_pdf(prestamo_id, cliente, monto_credito, fecha_pago, valor_pagado, titulo="RECIBO DE PAGO", subtitulo="VALOR PAGADO"):
    ruta_pdf = os.path.join(tempfile.gettempdir(), f"recibo_{prestamo_id}.pdf")
    doc = SimpleDocTemplate(ruta_pdf, pagesize=pagesizes.A4, rightMargin=42, leftMargin=42, topMargin=38, bottomMargin=34)
    estilos = getSampleStyleSheet()
    azul_oscuro = colors.HexColor("#0F172A")
    azul = colors.HexColor("#1D4ED8")
    gris = colors.HexColor("#64748B")
    gris_claro = colors.HexColor("#E2E8F0")
    fondo = colors.HexColor("#F8FAFC")
    exito = colors.HexColor("#166534")
    style_brand = ParagraphStyle('PdfBrand', parent=estilos['Normal'], fontSize=18, leading=22, textColor=colors.white, alignment=TA_CENTER)
    style_band = ParagraphStyle('PdfBand', parent=estilos['Normal'], fontSize=10, leading=12, textColor=colors.white, alignment=TA_CENTER)
    style_title = ParagraphStyle('PdfTitle', parent=estilos['Heading1'], fontSize=20, leading=24, textColor=azul_oscuro, alignment=TA_CENTER, spaceAfter=6)
    style_subtitle = ParagraphStyle('PdfSubtitle', parent=estilos['Normal'], fontSize=10, leading=14, textColor=gris, alignment=TA_CENTER, spaceAfter=16)
    style_label = ParagraphStyle('PdfLabel', parent=estilos['Normal'], fontSize=9.2, leading=12, textColor=gris)
    style_value = ParagraphStyle('PdfValue', parent=estilos['Normal'], fontSize=11, leading=14, textColor=azul_oscuro)
    style_section = ParagraphStyle('PdfSection', parent=estilos['Normal'], fontSize=9, leading=12, textColor=gris, alignment=TA_CENTER)
    style_amount = ParagraphStyle('PdfAmount', parent=estilos['Normal'], fontSize=18, leading=22, textColor=exito, alignment=TA_CENTER)
    style_note = ParagraphStyle('PdfNote', parent=estilos['Normal'], fontSize=9.5, leading=14, textColor=gris)
    style_footer = ParagraphStyle('PdfFooter', parent=estilos['Normal'], fontSize=8.8, leading=12, textColor=gris, alignment=TA_CENTER)
    story = []
    header = Table([[Paragraph("<b>CREDDT CRNTECH</b>", style_brand)]], colWidths=[doc.width])
    header.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), azul_oscuro), ('TOPPADDING', (0, 0), (-1, -1), 14), ('BOTTOMPADDING', (0, 0), (-1, -1), 14)]))
    story.append(header)
    banda = Table([[Paragraph("Área Administrativa y Financiera", style_band)]], colWidths=[doc.width])
    banda.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), azul), ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
    story.append(banda)
    story.append(Spacer(1, 16))
    if os.path.exists("logo_creddt.png"):
        logo = Image("logo_creddt.png", width=1.55 * inch, height=0.72 * inch)
        logo.hAlign = 'CENTER'
        story.append(logo)
        story.append(Spacer(1, 10))
    story.append(Paragraph(titulo, style_title))
    story.append(Paragraph("Documento soporte generado automáticamente por el sistema de créditos.", style_subtitle))
    resumen = Table([
        [Paragraph("N.° de crédito", style_label), Paragraph(f"<b>{prestamo_id}</b>", style_value), Paragraph("Fecha de operación", style_label), Paragraph(f"<b>{fecha_pago}</b>", style_value)],
        [Paragraph("Cliente", style_label), Paragraph(f"<b>{cliente}</b>", style_value), Paragraph("Capital del crédito", style_label), Paragraph(f"<b>{pesos(monto_credito)}</b>", style_value)],
    ], colWidths=[doc.width * 0.18, doc.width * 0.32, doc.width * 0.18, doc.width * 0.32])
    resumen.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), fondo), ('BOX', (0, 0), (-1, -1), 1, gris_claro), ('INNERGRID', (0, 0), (-1, -1), 0.5, gris_claro), ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 9), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    story.append(resumen)
    story.append(Spacer(1, 14))
    destaque = Table([[Paragraph(subtitulo, style_section)], [Paragraph(f"<b>{pesos(valor_pagado)}</b>", style_amount)]], colWidths=[doc.width])
    destaque.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white), ('BOX', (0, 0), (-1, -1), 1.2, gris_claro), ('TOPPADDING', (0, 0), (-1, 0), 10), ('BOTTOMPADDING', (0, 0), (-1, 0), 4), ('TOPPADDING', (0, 1), (-1, 1), 4), ('BOTTOMPADDING', (0, 1), (-1, 1), 14)]))
    story.append(destaque)
    story.append(Spacer(1, 14))
    nota = Table([[Paragraph("El presente documento constituye soporte formal del movimiento registrado en la plataforma CREDDT CRNTECH. Conserve este comprobante para control interno, conciliación y soporte de futuras validaciones.", style_note)]], colWidths=[doc.width])
    nota.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), fondo), ('BOX', (0, 0), (-1, -1), 1, gris_claro), ('TOPPADDING', (0, 0), (-1, -1), 12), ('BOTTOMPADDING', (0, 0), (-1, -1), 12), ('LEFTPADDING', (0, 0), (-1, -1), 12), ('RIGHTPADDING', (0, 0), (-1, -1), 12)]))
    story.append(nota)
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=1, color=gris_claro))
    story.append(Spacer(1, 10))
    story.append(Paragraph("CREDDT CRNTECH • Área Administrativa y Financiera • Documento generado automáticamente", style_footer))
    doc.build(story)
    return ruta_pdf


def generar_contrato_pdf(prestamo_id, cliente, monto_credito, cuotas, valor_cuota, tipo_credito, fecha_emision=None):
    ruta_pdf = os.path.join(tempfile.gettempdir(), f"contrato_{prestamo_id}.pdf")
    fecha_emision = fecha_emision or date.today().isoformat()
    doc = SimpleDocTemplate(ruta_pdf, pagesize=pagesizes.A4, rightMargin=40, leftMargin=40, topMargin=36, bottomMargin=34)
    estilos = getSampleStyleSheet()
    azul_oscuro = colors.HexColor("#0F172A")
    azul = colors.HexColor("#1D4ED8")
    gris = colors.HexColor("#64748B")
    gris_claro = colors.HexColor("#E2E8F0")
    fondo = colors.HexColor("#F8FAFC")
    style_brand = ParagraphStyle('ContratoBrand', parent=estilos['Normal'], fontSize=18, leading=22, textColor=colors.white, alignment=TA_CENTER)
    style_band = ParagraphStyle('ContratoBand', parent=estilos['Normal'], fontSize=10, leading=12, textColor=colors.white, alignment=TA_CENTER)
    style_title = ParagraphStyle('ContratoTitle', parent=estilos['Heading1'], fontSize=20, leading=24, textColor=azul_oscuro, alignment=TA_CENTER, spaceAfter=6)
    style_subtitle = ParagraphStyle('ContratoSubtitle', parent=estilos['Normal'], fontSize=10, leading=14, textColor=gris, alignment=TA_CENTER, spaceAfter=14)
    style_label = ParagraphStyle('ContratoLabel', parent=estilos['Normal'], fontSize=9.2, leading=12, textColor=gris)
    style_value = ParagraphStyle('ContratoValue', parent=estilos['Normal'], fontSize=11, leading=14, textColor=azul_oscuro)
    style_clause_title = ParagraphStyle('ContratoClauseTitle', parent=estilos['Normal'], fontSize=10.8, leading=14, textColor=azul_oscuro, spaceAfter=4)
    style_clause = ParagraphStyle('ContratoClause', parent=estilos['Normal'], fontSize=9.8, leading=15, textColor=colors.black, spaceAfter=8)
    style_footer = ParagraphStyle('ContratoFooter', parent=estilos['Normal'], fontSize=8.8, leading=12, textColor=gris, alignment=TA_CENTER)
    story = []
    header = Table([[Paragraph("<b>CREDDT CRNTECH</b>", style_brand)]], colWidths=[doc.width])
    header.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), azul_oscuro), ('TOPPADDING', (0, 0), (-1, -1), 14), ('BOTTOMPADDING', (0, 0), (-1, -1), 14)]))
    story.append(header)
    banda = Table([[Paragraph("Área de Aprobación", style_band)]], colWidths=[doc.width])
    banda.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), azul), ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
    story.append(banda)
    story.append(Spacer(1, 16))
    if os.path.exists("logo_creddt.png"):
        logo = Image("logo_creddt.png", width=1.75 * inch, height=0.8 * inch)
        logo.hAlign = 'CENTER'
        story.append(logo)
        story.append(Spacer(1, 10))
    story.append(Paragraph("CONTRATO DE CRÉDITO", style_title))
    story.append(Paragraph("Documento de aprobación y formalización de la operación", style_subtitle))
    resumen = Table([
        [Paragraph("Crédito", style_label), Paragraph(f"<b>{prestamo_id}</b>", style_value), Paragraph("Fecha de emisión", style_label), Paragraph(f"<b>{fecha_emision}</b>", style_value)],
        [Paragraph("Cliente", style_label), Paragraph(f"<b>{cliente}</b>", style_value), Paragraph("Tipo de crédito", style_label), Paragraph(f"<b>{tipo_credito}</b>", style_value)],
        [Paragraph("Monto aprobado", style_label), Paragraph(f"<b>{pesos(monto_credito)}</b>", style_value), Paragraph("Número de cuotas", style_label), Paragraph(f"<b>{cuotas}</b>", style_value)],
        [Paragraph("Valor de la cuota", style_label), Paragraph(f"<b>{pesos(valor_cuota)}</b>", style_value), Paragraph("Estado inicial", style_label), Paragraph("<b>Pendiente de aceptación</b>", style_value)],
    ], colWidths=[doc.width * 0.18, doc.width * 0.32, doc.width * 0.18, doc.width * 0.32])
    resumen.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), fondo), ('BOX', (0, 0), (-1, -1), 1, gris_claro), ('INNERGRID', (0, 0), (-1, -1), 0.5, gris_claro), ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 9), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    story.append(resumen)
    story.append(Spacer(1, 16))
    story.append(Paragraph("<b>1. Objeto de la operación</b>", style_clause_title))
    story.append(Paragraph("Mediante el presente documento, CREDDT CRNTECH deja constancia de la aprobación inicial del crédito descrito en el resumen anterior y de las condiciones base de la operación financiera ofrecida al cliente.", style_clause))
    story.append(Paragraph("<b>2. Condiciones generales de pago</b>", style_clause_title))
    story.append(Paragraph("El cliente se compromete a atender oportunamente el pago de las cuotas pactadas en las fechas de vencimiento definidas por el sistema, de acuerdo con la frecuencia del crédito y las políticas internas aplicables.", style_clause))
    story.append(Paragraph("<b>3. Abonos extraordinarios y recalculo</b>", style_clause_title))
    story.append(Paragraph("Los abonos extraordinarios a capital, cuando sean aceptados y registrados, reducirán el saldo del crédito y podrán generar un recalculo del valor de las cuotas pendientes, manteniendo la estructura operativa definida por la entidad.", style_clause))
    story.append(Paragraph("<b>4. Aceptación electrónica</b>", style_clause_title))
    story.append(Paragraph("La aceptación del contrato mediante el enlace enviado al correo registrado del cliente tendrá validez como manifestación expresa de conformidad frente a la información, condiciones y trazabilidad de la operación aquí descrita.", style_clause))
    validacion = Table([[Paragraph("<b>Validación institucional:</b><br/>La presente aprobación queda sujeta a verificación, aceptación del contrato por parte del cliente y continuidad del proceso operativo correspondiente.", style_clause)]], colWidths=[doc.width])
    validacion.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), fondo), ('BOX', (0, 0), (-1, -1), 1, gris_claro), ('TOPPADDING', (0, 0), (-1, -1), 12), ('BOTTOMPADDING', (0, 0), (-1, -1), 12), ('LEFTPADDING', (0, 0), (-1, -1), 12), ('RIGHTPADDING', (0, 0), (-1, -1), 12)]))
    story.append(validacion)
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=1, color=gris_claro))
    story.append(Spacer(1, 10))
    story.append(Paragraph("CREDDT CRNTECH • Área de Aprobación • Documento generado automáticamente", style_footer))
    doc.build(story)
    return ruta_pdf

def obtener_datos_cliente(conn, cedula):
    return conn.execute(text("""
        SELECT nombres || ' ' || apellidos AS nombre, correo
        FROM clientes
        WHERE cedula = :cedula
    """), {"cedula": cedula}).fetchone()

def enviar_pdf_por_correo(destino, asunto, cuerpo, ruta_pdf, nombre_adj, html_override=None):
    with open(ruta_pdf, "rb") as f:
        return enviar_correo_async(destino=destino, asunto=asunto, cuerpo=cuerpo, attachment_bytes=f.read(), attachment_name=nombre_adj, html_override=html_override)


def enviar_contrato_credito(prestamo_row):
    if not prestamo_row.get("correo"):
        return False, "Cliente sin correo registrado"
    token = prestamo_row.get("contrato_token")
    if not token:
        token = uuid.uuid4().hex
        with get_conn() as conn:
            conn.execute(text("UPDATE prestamos SET contrato_token = :token WHERE id = :id"), {"token": token, "id": prestamo_row["id"]})
            conn.commit()
    enlace = f"{APP_BASE_URL}?aceptar={token}" if APP_BASE_URL else None
    ruta_pdf = None
    try:
        ruta_pdf = generar_contrato_pdf(prestamo_row["id"], prestamo_row["cliente"], prestamo_row["monto_original"], prestamo_row["cuotas"], prestamo_row["valor_cuota"], prestamo_row["tipo"])
        cuerpo = construir_cuerpo_correo("CONTRATO", prestamo_row["cliente"], prestamo_id=prestamo_row["id"], monto=prestamo_row["monto_original"], cuotas=prestamo_row["cuotas"], valor_cuota=prestamo_row["valor_cuota"], tipo_credito=prestamo_row.get("tipo"), link_aceptacion=enlace)
        html_correo = construir_html_correo("CONTRATO", prestamo_row["cliente"], prestamo_id=prestamo_row["id"], monto=prestamo_row["monto_original"], cuotas=prestamo_row["cuotas"], valor_cuota=prestamo_row["valor_cuota"], tipo_credito=prestamo_row.get("tipo"), link_aceptacion=enlace)
        with open(ruta_pdf, "rb") as f:
            ok_mail, err_mail = enviar_correo_async(prestamo_row["correo"], "CREDDT CRNTECH | Contrato de crédito para aceptación", cuerpo, attachment_bytes=f.read(), attachment_name=f"contrato_{prestamo_row['id']}.pdf", html_override=html_correo)
        if ok_mail:
            with get_conn() as conn:
                conn.execute(text("""
                    UPDATE prestamos
                    SET contrato_enviado = 1,
                        fecha_envio_contrato = :fecha
                    WHERE id = :id
                """), {"fecha": datetime.now().isoformat(timespec='seconds'), "id": prestamo_row["id"]})
                conn.commit()
        return ok_mail, err_mail
    finally:
        if ruta_pdf and os.path.exists(ruta_pdf):
            try:
                os.remove(ruta_pdf)
            except Exception:
                pass


def enviar_correo_desembolso_credito(prestamo_row):
    if not prestamo_row.get("correo"):
        return False, "Cliente sin correo registrado"
    cuerpo = construir_cuerpo_correo("DESEMBOLSO", prestamo_row["cliente"], prestamo_id=prestamo_row["id"], tipo_credito=prestamo_row.get("tipo"), monto=prestamo_row["monto_original"], frecuencia=prestamo_row.get("frecuencia", "Mensual"), cuotas=prestamo_row["cuotas"], valor_cuota=prestamo_row["valor_cuota"])
    html_correo = construir_html_correo("DESEMBOLSO", prestamo_row["cliente"], prestamo_id=prestamo_row["id"], tipo_credito=prestamo_row.get("tipo"), monto=prestamo_row["monto_original"], frecuencia=prestamo_row.get("frecuencia", "Mensual"), cuotas=prestamo_row["cuotas"], valor_cuota=prestamo_row["valor_cuota"])
    ok_mail, err_mail = enviar_correo_async(prestamo_row["correo"], f"CREDDT CRNTECH | Confirmación de desembolso del crédito {prestamo_row['id']}", cuerpo, html_override=html_correo)
    if ok_mail:
        with get_conn() as conn:
            conn.execute(text("""
                UPDATE prestamos
                SET desembolso_notificado = 1,
                    fecha_desembolso = COALESCE(fecha_desembolso, :fecha)
                WHERE id = :id
            """), {"fecha": datetime.now().isoformat(timespec='seconds'), "id": prestamo_row["id"]})
            conn.commit()
    return ok_mail, err_mail

def guardar_cliente_db(data):
    with get_conn() as conn:
        conn.execute(text("""
            INSERT INTO clientes (cedula, nombres, apellidos, ciudad, telefono, correo, direccion, empresa, fecha_nacimiento, cargo)
            VALUES (:cedula, :nombres, :apellidos, :ciudad, :telefono, :correo, :direccion, :empresa, :fecha_nacimiento, :cargo)
        """), data)
        conn.commit()
def actualizar_cliente_db(cedula, data):
    with get_conn() as conn:
        conn.execute(text("""
            UPDATE clientes
            SET nombres=:nombres, apellidos=:apellidos, ciudad=:ciudad, telefono=:telefono, correo=:correo,
                direccion=:direccion, empresa=:empresa, fecha_nacimiento=:fecha_nacimiento, cargo=:cargo
            WHERE cedula=:cedula
        """), {**data, "cedula": cedula})
        conn.commit()
def eliminar_cliente_db(cedula):
    with get_conn() as conn:
        existe = conn.execute(text("SELECT COUNT(*) FROM prestamos WHERE cliente_cedula = :cedula"), {"cedula": cedula}).scalar()
        if int(existe or 0) > 0:
            return False, "No se puede eliminar el cliente porque tiene créditos asociados"
        conn.execute(text("DELETE FROM clientes WHERE cedula = :cedula"), {"cedula": cedula})
        conn.commit()
    return True, None

def _parse_fecha_cliente(valor):
    if valor in (None, "", "None"):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except Exception:
        return None

def _fecha_cliente_db(valor):
    if not valor:
        return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor).strip()
def crear_credito_db(cliente_cedula, monto, cuotas, frecuencia, tipo, fecha_inicio=None):
    fecha_inicio = fecha_inicio or date.today()
    monto = float(monto or 0)
    cuotas = int(cuotas or 0)
    frecuencia = str(frecuencia or "Mensual").title()
    tipo = str(tipo or "Normal").title()
    if monto <= 0 or cuotas <= 0:
        return False, "Monto o cuotas inválidas", None
    with get_conn() as conn:
        cliente = conn.execute(text("SELECT cedula, nombres, apellidos, correo FROM clientes WHERE cedula = :cedula"), {"cedula": cliente_cedula}).mappings().first()
        if not cliente:
            return False, "El cliente no está registrado", None
        prestamo_id = obtener_nuevo_id_prestamo("P")
        contrato_token = uuid.uuid4().hex
        if tipo == "Express":
            tasa_mensual = calcular_tasa_express(frecuencia)
            valor_cuota = calcular_cuota_express(monto, cuotas, frecuencia)
        else:
            tasa_mensual = calcular_tasa_normal(cuotas)
            valor_cuota = calcular_cuota_normal(monto, cuotas, frecuencia)
        conn.execute(text("""
            INSERT INTO prestamos (id, cliente_cedula, monto_original, cuotas, frecuencia, valor_cuota, estado, tipo,
                                   saldo_capital, tasa_mensual, contrato_aceptado, contrato_token, fecha_inicio)
            VALUES (:id, :cliente_cedula, :monto_original, :cuotas, :frecuencia, :valor_cuota, 'Pendiente', :tipo,
                    :saldo_capital, :tasa_mensual, 0, :contrato_token, :fecha_inicio)
        """), {
            "id": prestamo_id,
            "cliente_cedula": cliente_cedula,
            "monto_original": monto,
            "cuotas": cuotas,
            "frecuencia": frecuencia,
            "valor_cuota": valor_cuota,
            "tipo": tipo,
            "saldo_capital": monto,
            "tasa_mensual": tasa_mensual,
            "contrato_token": contrato_token,
            "fecha_inicio": fecha_inicio.isoformat()
        })
        for nro in range(1, cuotas + 1):
            fecha_v = calcular_fecha_vencimiento(fecha_inicio, nro, frecuencia)
            conn.execute(text("""
                INSERT INTO cuotas (prestamo_id, nro_cuota, fecha_vencimiento, valor_cuota, estado)
                VALUES (:prestamo_id, :nro_cuota, :fecha_vencimiento, :valor_cuota, 'Pendiente')
            """), {
                "prestamo_id": prestamo_id,
                "nro_cuota": nro,
                "fecha_vencimiento": fecha_v.isoformat(),
                "valor_cuota": valor_cuota
            })
        conn.commit()
        prestamo_row = {
            "id": prestamo_id,
            "cliente": f"{cliente['nombres']} {cliente['apellidos']}",
            "correo": cliente['correo'],
            "monto_original": monto,
            "cuotas": cuotas,
            "frecuencia": frecuencia,
            "valor_cuota": valor_cuota,
            "tipo": tipo,
            "contrato_token": contrato_token
        }
    ok_mail, err_mail = enviar_contrato_credito(prestamo_row)
    return True, None if ok_mail else err_mail, prestamo_row

def aceptar_contrato_por_token(token):
    with get_conn() as conn:
        prestamo = conn.execute(text("""
            SELECT p.id, p.cliente_cedula, p.monto_original, p.cuotas, p.frecuencia, p.valor_cuota, p.tipo, p.estado,
                   p.contrato_aceptado, p.contrato_token, c.nombres || ' ' || c.apellidos AS cliente, c.correo
            FROM prestamos p
            JOIN clientes c ON c.cedula = p.cliente_cedula
            WHERE p.contrato_token = :token
        """), {"token": token}).mappings().first()
        if not prestamo:
            return False, "Enlace inválido o vencido", None
        if int(prestamo["contrato_aceptado"] or 0) == 1:
            return True, "El contrato ya había sido aceptado previamente.", dict(prestamo)
        conn.execute(text("""
            UPDATE prestamos
            SET contrato_aceptado = 1,
                estado = 'Activo',
                fecha_aceptacion = :fecha
            WHERE id = :id
        """), {"fecha": datetime.now().isoformat(timespec='seconds'), "id": prestamo["id"]})
        conn.commit()
    prestamo_row = dict(prestamo)
    try:
        ok_mail, err_mail = enviar_correo_desembolso_credito(prestamo_row)
        if ok_mail:
            return True, "Contrato aceptado correctamente y correo de desembolso enviado.", prestamo_row
        return True, f"Contrato aceptado correctamente, pero el correo de desembolso no se pudo enviar: {err_mail}", prestamo_row
    except Exception as e:
        return True, f"Contrato aceptado correctamente, pero ocurrió un error enviando el correo de desembolso: {e}", prestamo_row


def procesar_recordatorios_automaticos():
    enviados = 0
    tipos_permitidos = {-3: "D-3", -1: "D-1", 0: "D0", 1: "D+1", 5: "D+5"}
    with get_conn() as conn:
        rows = conn.execute(text("""
            SELECT cu.id_cuota, cu.prestamo_id, cu.nro_cuota, cu.fecha_vencimiento::date AS fecha_vencimiento, cu.valor_cuota,
                   c.nombres || ' ' || c.apellidos AS cliente, c.correo
            FROM cuotas cu
            JOIN prestamos p ON p.id = cu.prestamo_id
            JOIN clientes c ON c.cedula = p.cliente_cedula
            WHERE cu.estado IN ('Pendiente', 'Parcial')
              AND c.correo IS NOT NULL
              AND cu.fecha_vencimiento::date BETWEEN CURRENT_DATE - INTERVAL '5 day' AND CURRENT_DATE + INTERVAL '3 day'
        """)).mappings().all()
        for r in rows:
            dias = (r['fecha_vencimiento'] - date.today()).days
            if dias not in tipos_permitidos:
                continue
            tipo_r = tipos_permitidos[dias]
            ya = conn.execute(text("SELECT COUNT(*) FROM reminders_sent WHERE id_cuota = :id_cuota AND tipo_recordatorio = :tipo"), {"id_cuota": r['id_cuota'], "tipo": tipo_r}).scalar()
            if int(ya or 0) > 0:
                continue
            cuerpo = construir_cuerpo_correo('RECORDATORIO', r['cliente'], prestamo_id=r['prestamo_id'], cuota_nro=r['nro_cuota'], fecha_vencimiento=r['fecha_vencimiento'], valor=r['valor_cuota'])
            html_correo = construir_html_correo('RECORDATORIO', r['cliente'], prestamo_id=r['prestamo_id'], cuota_nro=r['nro_cuota'], fecha_vencimiento=r['fecha_vencimiento'], valor=r['valor_cuota'])
            ok, _ = enviar_correo_async(r['correo'], f"CREDDT CRNTECH | Recordatorio de pago del crédito {r['prestamo_id']}", cuerpo, html_override=html_correo)
            if ok:
                conn.execute(text("INSERT INTO reminders_sent (id_cuota, tipo_recordatorio, fecha_envio) VALUES (:id_cuota, :tipo, :fecha_envio)"), {"id_cuota": r['id_cuota'], "tipo": tipo_r, "fecha_envio": datetime.now().isoformat(timespec='seconds')})
                enviados += 1
        conn.commit()
    return enviados

def render_aceptacion_contrato(token):
    st.markdown("<h2 style='text-align:center;'>CREDDT | CRNTECH</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#666;'>Aceptación de contrato de crédito</p>", unsafe_allow_html=True)
    with get_conn() as conn:
        prestamo = conn.execute(text("""
            SELECT p.id, p.monto_original, p.cuotas, p.frecuencia, p.valor_cuota, p.tipo, p.estado, p.contrato_aceptado,
                   c.nombres || ' ' || c.apellidos AS cliente
            FROM prestamos p
            JOIN clientes c ON c.cedula = p.cliente_cedula
            WHERE p.contrato_token = :token
        """), {"token": token}).mappings().first()
    if not prestamo:
        st.error("❌ El enlace de aceptación no es válido.")
        return
    st.markdown(f"### Crédito {prestamo['id']}")
    st.markdown(f"**Cliente:** {prestamo['cliente']}")
    st.markdown(f"**Tipo:** {prestamo['tipo']}")
    st.markdown(f"**Monto:** {pesos(prestamo['monto_original'])}")
    st.markdown(f"**Frecuencia:** {prestamo['frecuencia']}")
    st.markdown(f"**Cuotas:** {prestamo['cuotas']}")
    st.markdown(f"**Valor cuota:** {pesos(prestamo['valor_cuota'])}")
    if int(prestamo['contrato_aceptado'] or 0) == 1:
        st.success("✅ Este contrato ya fue aceptado previamente.")
        return
    st.info("Al hacer clic en aceptar, su crédito quedará activado para continuar con el desembolso.")
    if st.button("✅ Aceptar contrato", type="primary", disabled=st.session_state.get("app_busy", False)):
        start_busy("Aceptando contrato...")
        try:
            ok, mensaje, _ = aceptar_contrato_por_token(token)
            if ok:
                st.success(mensaje)
            else:
                st.error(mensaje)
        finally:
            stop_busy()
def enviar_recordatorio_credito(prestamo_row):
    if not prestamo_row.get("correo"):
        return False, "Cliente sin correo registrado"
    with get_conn() as conn:
        proxima = obtener_proxima_cuota(conn, prestamo_row["id"])
    if not proxima:
        return False, "El crédito no tiene cuotas pendientes"
    cuerpo = construir_cuerpo_correo(
        "RECORDATORIO",
        prestamo_row["cliente"],
        prestamo_id=prestamo_row["id"],
        cuota_nro=proxima[1],
        fecha_vencimiento=proxima[3],
        valor=proxima[2]
    )
    return enviar_correo_async(
        prestamo_row["correo"],
        f"Recordatorio de pago crédito {prestamo_row['id']}",
        cuerpo
    )
def actualizar_estado_prestamo(conn, prestamo_id):
    pendientes = conn.execute(text("""
        SELECT COUNT(*)
        FROM cuotas
        WHERE prestamo_id = :id AND estado <> 'Pagada'
    """), {"id": prestamo_id}).scalar()
    nuevo_estado = 'Cancelado' if int(pendientes or 0) == 0 else 'Activo'
    conn.execute(text("UPDATE prestamos SET estado = :estado WHERE id = :id"), {"estado": nuevo_estado, "id": prestamo_id})
def registrar_pago_cuota(prestamo_id, fecha_pago):
    with get_conn() as conn:
        prestamo_db = conn.execute(text("""
            SELECT id, cliente_cedula, monto_original, COALESCE(saldo_capital, monto_original) AS saldo_capital,
                   COALESCE(tasa_mensual, 0) AS tasa_mensual, valor_cuota
            FROM prestamos
            WHERE id = :id
        """), {"id": prestamo_id}).mappings().first()
        if not prestamo_db:
            return {"ok": False, "error": "No se pudo obtener el préstamo"}
        proxima = obtener_proxima_cuota(conn, prestamo_id)
        if not proxima:
            return {"ok": False, "error": "Todas las cuotas ya están pagadas"}
        id_cuota, nro_cuota, valor_cuota, fecha_vencimiento, _ = proxima
        valor_pago = normalizar_decimal(valor_cuota)
        saldo_capital_actual = normalizar_decimal(prestamo_db["saldo_capital"])
        tasa_mensual = Decimal(str(prestamo_db["tasa_mensual"] or 0))
        interes_periodo = (saldo_capital_actual * tasa_mensual).quantize(Decimal("0.01")) if tasa_mensual > 0 else Decimal("0.00")
        capital_pagado = valor_pago - interes_periodo
        if capital_pagado < 0:
            capital_pagado = Decimal("0.00")
        nuevo_saldo_capital = saldo_capital_actual - capital_pagado
        if nuevo_saldo_capital < 0:
            nuevo_saldo_capital = Decimal("0.00")
        result_pago = conn.execute(text("""
            INSERT INTO pagos (prestamo_id, fecha_pago, valor, estado, tipo_movimiento, detalle)
            VALUES (:id, :fecha, :valor, 'Pagado', 'CUOTA', :detalle)
            RETURNING id_pago
        """), {
            "id": prestamo_id,
            "fecha": fecha_pago.isoformat(),
            "valor": valor_pago,
            "detalle": f"Pago cuota #{nro_cuota}"
        })
        id_pago = result_pago.fetchone()[0]
        conn.execute(text("""
            INSERT INTO pagos_cuotas (id_pago, id_cuota, valor_aplicado)
            VALUES (:id_pago, :id_cuota, :valor_aplicado)
        """), {"id_pago": id_pago, "id_cuota": id_cuota, "valor_aplicado": valor_pago})
        conn.execute(text("UPDATE cuotas SET estado = 'Pagada' WHERE id_cuota = :id_cuota"), {"id_cuota": id_cuota})
        conn.execute(text("UPDATE prestamos SET saldo_capital = :saldo_capital WHERE id = :id"), {"saldo_capital": nuevo_saldo_capital, "id": prestamo_id})
        actualizar_estado_prestamo(conn, prestamo_id)
        conn.commit()
        cliente = obtener_datos_cliente(conn, prestamo_db["cliente_cedula"])
    nombre_cliente = cliente[0] if cliente else "Cliente"
    correo_cliente = (cliente[1] or "").strip() if cliente else ""
    pdf = None
    correo_ok = False
    correo_error = None
    try:
        pdf = generar_recibo_pdf(prestamo_id, nombre_cliente, prestamo_db["monto_original"], fecha_pago.isoformat(), valor_pago)
        cuerpo = construir_cuerpo_correo(
            "RECIBO_CUOTA",
            nombre_cliente,
            prestamo_id=prestamo_id,
            cuota_nro=nro_cuota,
            fecha_pago=fecha_pago.isoformat(),
            valor=valor_pago
        )
        if correo_cliente:
            correo_ok, correo_error = enviar_pdf_por_correo(
                correo_cliente,
                f"CREDDT CRNTECH | Confirmación de pago del crédito {prestamo_id}",
                cuerpo,
                pdf,
                f"recibo_{prestamo_id}.pdf",
                html_override=construir_html_correo(
                    "RECIBO_CUOTA",
                    nombre_cliente,
                    prestamo_id=prestamo_id,
                    cuota_nro=nro_cuota,
                    fecha_pago=fecha_pago.isoformat(),
                    valor=valor_pago
                )
            )
        else:
            correo_error = "Cliente sin correo registrado"
    finally:
        if pdf and os.path.exists(pdf):
            try:
                os.remove(pdf)
            except Exception:
                pass
    return {
        "ok": True,
        "credito": prestamo_id,
        "cuota": nro_cuota,
        "valor": valor_pago,
        "correo": correo_ok,
        "tiene_correo": bool(correo_cliente),
        "correo_error": correo_error
    }
def registrar_abono_capital(prestamo_id, fecha_pago, valor_abono):
    valor_abono = normalizar_decimal(valor_abono)
    if valor_abono <= 0:
        return {"ok": False, "error": "El abono a capital debe ser mayor a cero"}
    with get_conn() as conn:
        prestamo_db = conn.execute(text("""
            SELECT id, cliente_cedula, monto_original, COALESCE(saldo_capital, monto_original) AS saldo_capital,
                   COALESCE(tasa_mensual, 0) AS tasa_mensual, valor_cuota
            FROM prestamos
            WHERE id = :id
        """), {"id": prestamo_id}).mappings().first()
        if not prestamo_db:
            return {"ok": False, "error": "No se pudo obtener el préstamo"}
        cuotas_pendientes = conn.execute(text("""
            SELECT id_cuota, nro_cuota
            FROM cuotas
            WHERE prestamo_id = :id
              AND estado <> 'Pagada'
            ORDER BY nro_cuota ASC
        """), {"id": prestamo_id}).fetchall()
        if not cuotas_pendientes:
            return {"ok": False, "error": "No hay cuotas pendientes para recalcular"}
        saldo_capital_actual = normalizar_decimal(prestamo_db["saldo_capital"])
        if valor_abono >= saldo_capital_actual:
            return {"ok": False, "error": "El abono a capital no puede ser igual o mayor al saldo capital actual"}
        nuevo_saldo_capital = saldo_capital_actual - valor_abono
        cuotas_restantes = len(cuotas_pendientes)
        nueva_cuota = Decimal(str(calcular_cuota_amortizada(nuevo_saldo_capital, prestamo_db["tasa_mensual"], cuotas_restantes))).quantize(Decimal("0.01"))
        result_pago = conn.execute(text("""
            INSERT INTO pagos (prestamo_id, fecha_pago, valor, estado, tipo_movimiento, detalle)
            VALUES (:id, :fecha, :valor, 'Pagado', 'ABONO_CAPITAL', :detalle)
            RETURNING id_pago
        """), {
            "id": prestamo_id,
            "fecha": fecha_pago.isoformat(),
            "valor": valor_abono,
            "detalle": f"Abono a capital por {valor_abono}"
        })
        id_pago = result_pago.fetchone()[0]
        conn.execute(text("UPDATE prestamos SET saldo_capital = :saldo_capital, valor_cuota = :valor_cuota WHERE id = :id"), {
            "saldo_capital": nuevo_saldo_capital,
            "valor_cuota": nueva_cuota,
            "id": prestamo_id
        })
        for id_cuota, _ in cuotas_pendientes:
            conn.execute(text("UPDATE cuotas SET valor_cuota = :valor_cuota WHERE id_cuota = :id_cuota AND estado <> 'Pagada'"), {
                "valor_cuota": nueva_cuota,
                "id_cuota": id_cuota
            })
        actualizar_estado_prestamo(conn, prestamo_id)
        conn.commit()
        cliente = obtener_datos_cliente(conn, prestamo_db["cliente_cedula"])
    nombre_cliente = cliente[0] if cliente else "Cliente"
    correo_cliente = (cliente[1] or "").strip() if cliente else ""
    pdf = None
    correo_ok = False
    correo_error = None
    try:
        pdf = generar_recibo_pdf(prestamo_id, nombre_cliente, prestamo_db["monto_original"], fecha_pago.isoformat(), valor_abono, titulo="RECIBO DE ABONO A CAPITAL", subtitulo="ABONO A CAPITAL")
        cuerpo = construir_cuerpo_correo(
            "RECIBO_ABONO",
            nombre_cliente,
            prestamo_id=prestamo_id,
            fecha_pago=fecha_pago.isoformat(),
            valor=valor_abono,
            saldo_capital=nuevo_saldo_capital,
            nueva_cuota=nueva_cuota
        )
        if correo_cliente:
            correo_ok, correo_error = enviar_pdf_por_correo(
                correo_cliente,
                f"Abono a capital crédito {prestamo_id}",
                cuerpo,
                pdf,
                f"abono_capital_{prestamo_id}.pdf"
            )
        else:
            correo_error = "Cliente sin correo registrado"
    finally:
        if pdf and os.path.exists(pdf):
            try:
                os.remove(pdf)
            except Exception:
                pass
    return {
        "ok": True,
        "credito": prestamo_id,
        "valor": valor_abono,
        "nueva_cuota": nueva_cuota,
        "correo": correo_ok,
        "tiene_correo": bool(correo_cliente),
        "correo_error": correo_error
    }
# =========================
# ENVÍO DE CORREO
# =========================
def enviar_correo_brevo(
        destino,
        asunto,
        cuerpo,
        attachment_bytes=None,
        attachment_name=None,
        html_override=None
):
    try:
        destino = (destino or "").strip()
        if not destino:
            return False, "Cliente sin correo registrado"

        cuerpo = (cuerpo or "").strip()
        cuerpo_html = cuerpo.replace("\n", "<br>")

        html_template = f"""
        <div style="font-family: Arial, Helvetica, sans-serif; background-color: #f4f6f8; padding: 30px;">
            <div style="max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 10px; overflow: hidden; border: 1px solid #e5e7eb;">
                <div style="background: #0f172a; padding: 24px 30px;">
                    <h2 style="margin: 0; color: #ffffff; font-size: 22px;">CREDDT CRNTECH</h2>
                    <p style="margin: 8px 0 0 0; color: #cbd5e1; font-size: 14px;">Notificación automática</p>
                </div>
                <div style="padding: 30px; color: #1f2937; font-size: 15px; line-height: 1.7; white-space: normal;">
                    {cuerpo_html}
                </div>
                <div style="padding: 20px 30px; background: #f8fafc; border-top: 1px solid #e5e7eb; color: #64748b; font-size: 12px; line-height: 1.6;">
                    Este mensaje fue generado automáticamente por CREDDT CRNTECH.<br>
                    Si requiere soporte o validación adicional, puede responder a este correo.
                </div>
            </div>
        </div>
        """

        payload = {
            "sender": {
                "name": BREVO_FROM_NAME,
                "email": BREVO_FROM_EMAIL
            },
            "to": [
                {
                    "email": destino,
                    "name": destino
                }
            ],
            "subject": asunto,
            "textContent": cuerpo,
            "htmlContent": html_override or html_template
        }

        if attachment_bytes:
            payload["attachment"] = [
                {
                    "name": attachment_name or "adjunto.pdf",
                    "content": base64.b64encode(attachment_bytes).decode("utf-8")
                }
            ]

        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }

        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code in (200, 201, 202):
            return True, None

        detalle = response.text
        try:
            detalle_json = response.json()
            detalle = detalle_json
        except Exception:
            pass

        return False, f"Brevo {response.status_code}: {detalle}"

    except requests.Timeout:
        return False, "Timeout conectando con Brevo"
    except requests.RequestException as e:
        return False, f"Error de red con Brevo: {e}"
    except Exception as e:
        return False, f"Error general enviando correo: {e}"

def enviar_correo_async(
        destino,
        asunto,
        cuerpo,
        attachment_bytes=None,
        attachment_name=None,
        html_override=None
):
    return enviar_correo_brevo(
        destino=destino,
        asunto=asunto,
        cuerpo=cuerpo,
        attachment_bytes=attachment_bytes,
        attachment_name=attachment_name,
        html_override=html_override
    )

if token_aceptar:
    render_aceptacion_contrato(token_aceptar)
    st.stop()
# ==========================
# CARGAR ESTADO GENERAL
# ==========================
with get_conn() as conn:
    estado = pd.read_sql(
        text("""
        SELECT
            p.id,
            p.estado,
            p.monto_original,
            p.valor_cuota,
            p.cuotas,
            COALESCE(p.frecuencia, 'Mensual') AS frecuencia,
            p.tipo,
            p.cliente_cedula,
            COALESCE(p.contrato_aceptado, 0) AS contrato_aceptado,
            COALESCE(p.contrato_enviado, 0) AS contrato_enviado,
            COALESCE(p.desembolso_notificado, 0) AS desembolso_notificado,
            p.fecha_envio_contrato,
            p.fecha_aceptacion,
            p.fecha_desembolso,
            COALESCE(p.saldo_capital, p.monto_original) AS saldo_capital,
            COALESCE(p.tasa_mensual, 0) AS tasa_mensual,
            COALESCE(SUM(pg.valor),0) AS total_pagado,
            COALESCE((
                SELECT SUM(cu.valor_cuota)
                FROM cuotas cu
                WHERE cu.prestamo_id = p.id
                  AND cu.estado <> 'Pagada'
            ),0) AS saldo,
            COALESCE(SUM(pg.valor),0) + COALESCE((
                SELECT SUM(cu.valor_cuota)
                FROM cuotas cu
                WHERE cu.prestamo_id = p.id
                  AND cu.estado <> 'Pagada'
            ),0) AS monto_total_credito,
            c.nombres || ' ' || c.apellidos AS cliente,
            c.correo
        FROM prestamos p
        LEFT JOIN pagos pg
            ON pg.prestamo_id = p.id
        LEFT JOIN clientes c
            ON c.cedula = p.cliente_cedula
        GROUP BY
            p.id, p.estado, p.monto_original, p.valor_cuota, p.cuotas, p.frecuencia, p.tipo,
            p.cliente_cedula, p.contrato_aceptado, p.contrato_enviado, p.desembolso_notificado,
            p.fecha_envio_contrato, p.fecha_aceptacion, p.fecha_desembolso,
            p.saldo_capital, p.tasa_mensual, c.nombres, c.apellidos, c.correo
        ORDER BY p.id DESC
        """),
        conn
    )
# asegurar tipos numéricos
for col in [
    "monto_original",
    "monto_total_credito",
    "valor_cuota",
    "total_pagado",
    "saldo",
    "saldo_capital",
    "tasa_mensual"
]:
    if col in estado.columns:
        estado[col] = pd.to_numeric(estado[col])
if "recordatorios_auto" not in st.session_state:
    try:
        st.session_state.recordatorios_auto = procesar_recordatorios_automaticos()
    except Exception:
        st.session_state.recordatorios_auto = 0
# ==========================
# CALCULAR ALERTAS
# ==========================
clientes_mora = 0
monto_mora = 0
with get_conn() as conn:
    mora_df = pd.read_sql(
        """
        SELECT
            COUNT(DISTINCT prestamo_id) as clientes_mora,
            COALESCE(SUM(valor_cuota),0) as monto_mora
        FROM cuotas
        WHERE estado <> 'Pagada'
        AND fecha_vencimiento::date < CURRENT_DATE
        """,
        conn
    )
    if not mora_df.empty:
        clientes_mora = int(mora_df["clientes_mora"][0])
        monto_mora = float(mora_df["monto_mora"][0])
# ==========================
# FUNCIONES SIMULADOR
# ==========================
def calcular_tasa_normal(cuotas):
    if int(cuotas) == 12:
        return 0.0427
    if int(cuotas) == 15:
        return 0.0433
    return 0.0427
def calcular_tasa_express(frecuencia):
    return 0.10 if str(frecuencia).lower() == "mensual" else 0.055
def calcular_cuota_normal(monto, cuotas, frecuencia="Mensual"):
    monto = float(monto or 0)
    cuotas = int(cuotas or 0)
    if monto <= 0 or cuotas <= 0:
        return 0
    tasa = calcular_tasa_normal(cuotas)
    cuota_base = monto / cuotas
    interes_total = monto * tasa
    valor_cuota = cuota_base + interes_total
    if str(frecuencia).lower() == "quincenal":
        valor_cuota /= 2
    valor_cuota = round(valor_cuota / 1000) * 1000
    return round(valor_cuota)
def calcular_cuota_express(monto, cuotas, frecuencia):
    monto = float(monto or 0)
    cuotas = int(cuotas or 0)
    if monto <= 0 or cuotas <= 0:
        return 0
    tasa = calcular_tasa_express(frecuencia)
    cuota_base = monto / cuotas
    interes_total = monto * tasa
    valor_cuota = cuota_base + interes_total
    valor_cuota = round(valor_cuota / 100) * 100
    return round(valor_cuota)
def calcular_fecha_vencimiento(fecha_inicio, nro_cuota, frecuencia):
    dias = 30 if str(frecuencia).lower() == "mensual" else 15
    return fecha_inicio + timedelta(days=dias * nro_cuota)
def obtener_nuevo_id_prestamo(prefix="P"):
    return prefix + uuid.uuid4().hex[:6].upper()
# ==========================
# TABS
# ==========================
_tabs_labels = ["📊 Resumen"]
if PUEDE_VER_CLIENTES:
    _tabs_labels.append("👥 Clientes")
if PUEDE_CREAR_CREDITOS:
    _tabs_labels.append("🆕 Nuevo crédito")
if PUEDE_VER_DETALLE:
    _tabs_labels.append("📄 Detalle por crédito")
if PUEDE_REGISTRAR_PAGOS:
    _tabs_labels.append("💰 Pagos")
if PUEDE_USAR_SIMULADOR:
    _tabs_labels.append("🧮 Simulador")

_tabs_objs = st.tabs(_tabs_labels)
_tabs_map = dict(zip(_tabs_labels, _tabs_objs))

tab_resumen = _tabs_map["📊 Resumen"]
tab_clientes = _tabs_map.get("👥 Clientes")
tab_creditos = _tabs_map.get("🆕 Nuevo crédito")
tab_detalle = _tabs_map.get("📄 Detalle por crédito")
tab_pagos = _tabs_map.get("💰 Pagos")
tab_sim = _tabs_map.get("🧮 Simulador")
# ==========================
# 📊 RESUMEN
# ==========================
with tab_resumen:
    st.subheader("📊 Resumen general")
    if st.session_state.get("recordatorios_auto", 0):
        enviados_auto = st.session_state.get("recordatorios_auto", 0)
        st.success(f"✅ Recordatorios automáticos enviados en esta sesión: {enviados_auto}")
    total_colocado = estado["monto_original"].sum()
    total_cobrado = estado["total_pagado"].sum()
    saldo_pendiente = estado["saldo"].sum()
    creditos_activos = estado[estado["estado"] != "Cancelado"].shape[0]
    exposicion_mora_total = 0 if saldo_pendiente <= 0 else (monto_mora / saldo_pendiente) * 100
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Total colocado", pesos(total_colocado))
    k2.metric("✅ Total cobrado", pesos(total_cobrado))
    k3.metric("⏳ Saldo pendiente", pesos(saldo_pendiente))
    k4.metric("📄 Créditos activos", creditos_activos)
    render_section_divider("compact")
    df = estado.copy()
    for c in ["monto_original","monto_total_credito","total_pagado","saldo","valor_cuota"]:
        df[c] = df[c].apply(pesos)
    tabla_resumen = df[
        ["id","cliente","monto_original","monto_total_credito",
         "total_pagado","saldo","valor_cuota","cuotas","tipo","estado"]
    ].rename(columns={
        "id": "Crédito",
        "cliente": "Cliente",
        "monto_original": "Capital",
        "monto_total_credito": "Total del crédito",
        "total_pagado": "Pagado",
        "saldo": "Saldo pendiente",
        "valor_cuota": "Cuota",
        "cuotas": "N.° cuotas",
        "tipo": "Tipo de crédito",
        "estado": "Estado"
    })
    st.dataframe(tabla_resumen, use_container_width=True, hide_index=True)
    render_section_divider()
    st.subheader("⚠️ Alertas de cartera")
    st.caption("Haz clic en el indicador para ver el detalle de clientes con cuotas vencidas.")
    a1, a2, a3 = st.columns(3)
    with a1:
        if st.button("👥 Clientes en mora", key="btn_alerta_clientes_mora"):
            st.session_state.detalle_mora = "clientes"
        st.metric("", clientes_mora)
    with a2:
        if st.button("💸 Monto en mora", key="btn_alerta_monto_mora"):
            st.session_state.detalle_mora = "monto"
        st.metric("", pesos(monto_mora))
    with a3:
        if st.button("📌 Exposición en mora", key="btn_alerta_exposicion_mora"):
            st.session_state.detalle_mora = "exposicion"
        st.metric("", f"{exposicion_mora_total:.1f}%")
    if "detalle_mora" in st.session_state:
        with get_conn() as conn:
            detalle_mora_df = pd.read_sql(text("""
                SELECT
                    p.id,
                    c.nombres || ' ' || c.apellidos AS cliente,
                    COUNT(cu.id_cuota) AS cuotas_en_mora,
                    COALESCE(SUM(cu.valor_cuota),0) AS monto_en_mora,
                    COALESCE(MAX(p.saldo_capital),0) AS exposicion_en_mora
                FROM cuotas cu
                JOIN prestamos p ON p.id = cu.prestamo_id
                JOIN clientes c ON c.cedula = p.cliente_cedula
                WHERE cu.estado <> 'Pagada'
                  AND cu.fecha_vencimiento::date < CURRENT_DATE
                GROUP BY p.id, c.nombres, c.apellidos
            """), conn)
        if detalle_mora_df.empty:
            st.info("✅ No hay clientes en mora actualmente.")
        else:
            if st.session_state.detalle_mora == "monto":
                detalle_mora_df = detalle_mora_df.sort_values(["monto_en_mora", "cuotas_en_mora"], ascending=[False, False])
                titulo_mora = "💸 Detalle por monto en mora"
            elif st.session_state.detalle_mora == "exposicion":
                detalle_mora_df = detalle_mora_df.sort_values(["exposicion_en_mora", "monto_en_mora"], ascending=[False, False])
                titulo_mora = "📌 Detalle por exposición en mora"
            else:
                detalle_mora_df = detalle_mora_df.sort_values(["cuotas_en_mora", "monto_en_mora"], ascending=[False, False])
                titulo_mora = "👥 Clientes en mora"
            detalle_mora_show = detalle_mora_df.copy()
            detalle_mora_show["monto_en_mora"] = detalle_mora_show["monto_en_mora"].apply(pesos)
            detalle_mora_show["exposicion_en_mora"] = detalle_mora_show["exposicion_en_mora"].apply(pesos)
            detalle_mora_show = detalle_mora_show[["id", "cliente", "cuotas_en_mora", "monto_en_mora", "exposicion_en_mora"]].rename(columns={
                "id": "Crédito",
                "cliente": "Cliente",
                "cuotas_en_mora": "Cuotas en mora",
                "monto_en_mora": "Monto en mora",
                "exposicion_en_mora": "Exposición en mora"
            })
            st.markdown(f"### {titulo_mora}")
            st.dataframe(
                detalle_mora_show,
                use_container_width=True,
                hide_index=True
            )
    # ==========================
    # 🔎 CONSULTA MENSUAL
    # ==========================
    render_section_divider()
    st.subheader("🔎 Consulta mensual (corte 02 → 02)")
    meses_disponibles = pd.date_range("2025-12-01", "2030-12-01", freq="MS").strftime("%Y-%m").tolist()
    mes_actual = date.today().strftime("%Y-%m")
    index_actual = meses_disponibles.index(mes_actual) if mes_actual in meses_disponibles else 0

    mes_consulta = st.selectbox(
        "Selecciona el mes",
        meses_disponibles,
        index=index_actual
    )
    year, month = map(int, mes_consulta.split("-"))
    if year == 2025 and month == 12:
        inicio = datetime(2025,12,15)
        fin = datetime(2026,1,1)
    elif year == 2026 and month == 1:
        inicio = datetime(2026,1,1)
        fin = datetime(2026,2,2)
    else:
        inicio = datetime(year, month, 3)
        fin = datetime(year + (month==12), 1 if month==12 else month+1, 2)
    with get_conn() as conn:
        cuotas_df = pd.read_sql(text("""
            SELECT cu.fecha_vencimiento, cu.valor_cuota, cu.estado, cu.nro_cuota,
                   c.nombres || ' ' || c.apellidos AS cliente
            FROM cuotas cu
            JOIN prestamos p ON p.id = cu.prestamo_id
            JOIN clientes c ON c.cedula = p.cliente_cedula
            WHERE cu.fecha_vencimiento::date >= :inicio
            AND cu.fecha_vencimiento::date <= :fin
            ORDER BY cu.fecha_vencimiento
        """), conn, params={"inicio": inicio, "fin": fin})
    total_periodo = cuotas_df["valor_cuota"].sum() if not cuotas_df.empty else 0
    pagado_periodo = cuotas_df[cuotas_df["estado"]=="Pagada"]["valor_cuota"].sum() if not cuotas_df.empty else 0
    pendiente_periodo = cuotas_df[cuotas_df["estado"].isin(["Pendiente","Parcial"])]["valor_cuota"].sum() if not cuotas_df.empty else 0
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("📥 Cuotas del período", key="btn_total_periodo"):
            st.session_state.detalle = "total"
        st.metric("", pesos(total_periodo))
    with c2:
        if st.button("✅ Pagado en el período", key="btn_pagado_periodo"):
            st.session_state.detalle = "pagado"
        st.metric("", pesos(pagado_periodo))
    with c3:
        if st.button("⏳ Pendiente del período", key="btn_pendiente_periodo"):
            st.session_state.detalle = "pendiente"
        st.metric("", pesos(pendiente_periodo))
    if "detalle" in st.session_state and not cuotas_df.empty:
        st.divider()
        if st.session_state.detalle=="total":
            df_detalle=cuotas_df
            titulo="📋 Todas las cuotas"
        elif st.session_state.detalle=="pagado":
            df_detalle=cuotas_df[cuotas_df["estado"]=="Pagada"]
            titulo="✅ Pagadas"
        else:
            df_detalle=cuotas_df[cuotas_df["estado"].isin(["Pendiente","Parcial"])]
            titulo="⏳ Pendientes"
        st.markdown(f"### {titulo}")
        cols = st.columns(3)
        for i,r in enumerate(df_detalle.itertuples()):
            with cols[i%3]:
                estado_color = "🟢 Pagada" if r.estado=="Pagada" else "🟡 Parcial" if r.estado=="Parcial" else "🔴 Pendiente"
                st.markdown(f"""
                <div style="background:#ffffff;color:#111;border-radius:14px;padding:14px;
                            box-shadow:0 2px 6px rgba(0,0,0,.08);margin-bottom:14px;">
                    <div style="font-weight:600;font-size:15px;color:#000">{r.cliente}</div>
                    <div style="font-size:13px;color:#555;margin-top:4px;">
                        Cuota #{r.nro_cuota} · {r.fecha_vencimiento}
                    </div>
                    <div style="font-size:16px;font-weight:700;margin-top:6px;">
                        {pesos(r.valor_cuota)}
                    </div>
                    <div style="font-size:13px;margin-top:4px;">{estado_color}</div>
                </div>
                """, unsafe_allow_html=True)
# ==========================
# 👥 CLIENTES
# ==========================
if tab_clientes is not None:
    with tab_clientes:
        st.subheader("👥 Gestión de clientes")
        show_flash("clientes_msg")

        with get_conn() as conn:
            clientes_df = pd.read_sql(
                text("""
                    SELECT cedula, nombres, apellidos, ciudad, telefono, correo, direccion, empresa, fecha_nacimiento, cargo
                    FROM clientes
                    ORDER BY nombres, apellidos
                """),
                conn
            )

        _cli_labels = []
        if PUEDE_REGISTRAR_CLIENTES:
            _cli_labels.append("📝 Registrar cliente")
        if PUEDE_GESTIONAR_CLIENTES or PUEDE_BORRAR_CLIENTES:
            _cli_labels.append("🛠️ Gestión de clientes")
        _cli_labels.append("📋 BD clientes")
        _cli_tabs = st.tabs(_cli_labels)
        _cli_map = dict(zip(_cli_labels, _cli_tabs))
        cli_tab1 = _cli_map.get("📝 Registrar cliente")
        cli_tab2 = _cli_map.get("🛠️ Gestión de clientes")
        cli_tab3 = _cli_map.get("📋 BD clientes")

        if cli_tab1 is not None:
            with cli_tab1:
                with st.form("form_nuevo_cliente", clear_on_submit=True):
                    cedula_new = st.text_input("Cédula *")
                    nombres_new = st.text_input("Nombres *")
                    apellidos_new = st.text_input("Apellidos *")
                    ciudad_new = st.text_input("Ciudad")
                    telefono_new = st.text_input("Teléfono")
                    correo_new = st.text_input("Correo")
                    direccion_new = st.text_input("Dirección")
                    empresa_new = st.text_input("Empresa")
                    fecha_nacimiento_new = st.date_input(
                        "Fecha de nacimiento",
                        value=None,
                        min_value=date(1900, 1, 1),
                        max_value=date.today(),
                        format="YYYY-MM-DD"
                    )
                    cargo_new = st.text_input("Cargo")
                    guardar_cliente = st.form_submit_button("Guardar cliente", type="primary", disabled=st.session_state.get("app_busy", False))
                    if guardar_cliente:
                        if not cedula_new.strip() or not nombres_new.strip() or not apellidos_new.strip():
                            st.error("❌ Cédula, nombres y apellidos son obligatorios")
                        else:
                            start_busy("Registrando cliente...")
                            try:
                                guardar_cliente_db({
                                    "cedula": cedula_new.strip(),
                                    "nombres": nombres_new.strip(),
                                    "apellidos": apellidos_new.strip(),
                                    "ciudad": ciudad_new.strip(),
                                    "telefono": telefono_new.strip(),
                                    "correo": correo_new.strip(),
                                    "direccion": direccion_new.strip(),
                                    "empresa": empresa_new.strip(),
                                    "fecha_nacimiento": _fecha_cliente_db(fecha_nacimiento_new),
                                    "cargo": cargo_new.strip()
                                })
                                set_flash("clientes_msg", "success", "✅ Cliente registrado correctamente")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ No se pudo registrar el cliente: {e}")
                            finally:
                                stop_busy()

        if cli_tab2 is not None:
            with cli_tab2:
                if clientes_df.empty:
                    st.info("No hay clientes registrados.")
                else:
                    clientes_df = clientes_df.fillna("")
                    cliente_options = [None] + clientes_df["cedula"].tolist()
                    cliente_sel = st.selectbox(
                        "Selecciona un cliente",
                        cliente_options,
                        index=0,
                        format_func=lambda x: "Selecciona un cliente" if x is None else f"{x} — {clientes_df.loc[clientes_df['cedula']==x, 'nombres'].iloc[0]} {clientes_df.loc[clientes_df['cedula']==x, 'apellidos'].iloc[0]}",
                        key="sel_cliente_gestion"
                    )

                    if cliente_sel is None:
                        st.info("ℹ️ Selecciona un cliente para editar o borrar.")
                    else:
                        fila = clientes_df[clientes_df["cedula"] == cliente_sel].iloc[0]

                        col_g1, col_g2 = st.columns(2)

                        with col_g1:
                            if PUEDE_GESTIONAR_CLIENTES:
                                with st.expander("✏️ Editar cliente", expanded=True):
                                    with st.form("form_editar_cliente"):
                                        st.text_input("Cédula", value=fila["cedula"], disabled=True)
                                        nombres_edit = st.text_input("Nombres", value=fila["nombres"])
                                        apellidos_edit = st.text_input("Apellidos", value=fila["apellidos"])
                                        ciudad_edit = st.text_input("Ciudad", value=fila["ciudad"])
                                        telefono_edit = st.text_input("Teléfono", value=fila["telefono"])
                                        correo_edit = st.text_input("Correo", value=fila["correo"])
                                        direccion_edit = st.text_input("Dirección", value=fila["direccion"])
                                        empresa_edit = st.text_input("Empresa", value=fila["empresa"])
                                        fecha_nacimiento_edit = st.date_input(
                                            "Fecha de nacimiento",
                                            value=_parse_fecha_cliente(fila["fecha_nacimiento"]),
                                            min_value=date(1900, 1, 1),
                                            max_value=date.today(),
                                            format="YYYY-MM-DD",
                                            key="fecha_nacimiento_edit"
                                        )
                                        cargo_edit = st.text_input("Cargo", value=fila["cargo"])
                                        actualizar = st.form_submit_button("Guardar cambios", type="primary", disabled=st.session_state.get("app_busy", False))
                                        if actualizar:
                                            start_busy("Actualizando cliente...")
                                            try:
                                                actualizar_cliente_db(cliente_sel, {
                                                    "nombres": nombres_edit.strip(),
                                                    "apellidos": apellidos_edit.strip(),
                                                    "ciudad": ciudad_edit.strip(),
                                                    "telefono": telefono_edit.strip(),
                                                    "correo": correo_edit.strip(),
                                                    "direccion": direccion_edit.strip(),
                                                    "empresa": empresa_edit.strip(),
                                                    "fecha_nacimiento": _fecha_cliente_db(fecha_nacimiento_edit),
                                                    "cargo": cargo_edit.strip()
                                                })
                                                set_flash("clientes_msg", "success", "✅ Cliente actualizado correctamente")
                                                st.session_state["sel_cliente_gestion"] = None
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"❌ No se pudo actualizar el cliente: {e}")
                                            finally:
                                                stop_busy()

                        with col_g2:
                            if PUEDE_BORRAR_CLIENTES:
                                with st.expander("🗑️ Borrar cliente", expanded=False):
                                    st.warning("Esta acción eliminará el cliente solo si no tiene créditos asociados.")
                                    if st.button("Borrar cliente seleccionado", key="btn_borrar_cliente", type="secondary", disabled=st.session_state.get("app_busy", False)):
                                        start_busy("Eliminando cliente...")
                                        try:
                                            ok_del, err_del = eliminar_cliente_db(cliente_sel)
                                            if ok_del:
                                                st.session_state["sel_cliente_gestion"] = None
                                                set_flash("clientes_msg", "success", "✅ Cliente eliminado correctamente")
                                                st.rerun()
                                            else:
                                                st.error(f"❌ {err_del}")
                                        finally:
                                            stop_busy()

        if cli_tab3 is not None:
            with cli_tab3:
                if not clientes_df.empty:
                    st.dataframe(clientes_df.rename(columns={
                        "cedula": "Cédula",
                        "nombres": "Nombres",
                        "apellidos": "Apellidos",
                        "ciudad": "Ciudad",
                        "telefono": "Teléfono",
                        "correo": "Correo",
                        "direccion": "Dirección",
                        "empresa": "Empresa",
                        "fecha_nacimiento": "Fecha de nacimiento",
                        "cargo": "Cargo"
                    }), use_container_width=True, hide_index=True)
                else:
                    st.info("No hay clientes registrados.")
# ==========================
# 🆕 NUEVO CRÉDITO
# ==========================
if tab_creditos is not None:
    with tab_creditos:
            st.subheader("🆕 Registrar nuevo crédito")
            show_flash("credito_msg")
            show_flash("contrato_msg")

            with get_conn() as conn:
                clientes_credito_df = pd.read_sql(
                    text("SELECT cedula, nombres, apellidos, correo FROM clientes ORDER BY nombres, apellidos"),
                    conn
                )

            cred_tab1, cred_tab2, cred_tab3 = st.tabs([
                "💳 Crédito normal",
                "⚡ Crédito express",
                "📨 Contratos pendientes"
            ])

            if clientes_credito_df.empty:
                st.info("ℹ️ Primero registra un cliente para crear créditos.")
            else:
                cliente_options = [None] + clientes_credito_df["cedula"].tolist()
                nombre_cliente = lambda x: "Selecciona un cliente" if x is None else f"{x} — {clientes_credito_df.loc[clientes_credito_df['cedula']==x, 'nombres'].iloc[0]} {clientes_credito_df.loc[clientes_credito_df['cedula']==x, 'apellidos'].iloc[0]}"

                with cred_tab1:
                    with st.form("form_credito_normal", clear_on_submit=True):
                        cliente_normal = st.selectbox(
                            "Cliente",
                            cliente_options,
                            key="cliente_normal_credito",
                            format_func=nombre_cliente,
                            index=0
                        )
                        monto_normal_new = st.number_input("Monto a prestar", min_value=0.0, step=100000.0, value=1000000.0, key="nuevo_monto_normal")
                        cuotas_normal_new = st.selectbox("Número de cuotas", [12, 15], key="nuevo_cuotas_normal")
                        frecuencia_normal_new = st.selectbox("Frecuencia", ["Mensual", "Quincenal"], key="nuevo_frec_normal")
                        fecha_inicio_normal = st.date_input("Fecha de inicio", value=date.today(), key="fecha_inicio_normal")
                        st.caption("La simulación final se procesa al registrar el crédito.")
                        submit_normal = st.form_submit_button("Registrar crédito normal", type="primary", disabled=st.session_state.get("app_busy", False))
                    if submit_normal:
                        if cliente_normal is None:
                            st.warning("ℹ️ Selecciona un cliente para registrar un crédito normal.")
                        else:
                            start_busy("Creando crédito normal...")
                            try:
                                ok_c, err_c, prestamo_creado = crear_credito_db(cliente_normal, monto_normal_new, cuotas_normal_new, frecuencia_normal_new, "Normal", fecha_inicio_normal)
                                if ok_c:
                                    st.session_state["cliente_normal_credito"] = None
                                    if not err_c:
                                        set_flash("credito_msg", "success", f"✅ Crédito {prestamo_creado['id']} creado y contrato enviado correctamente")
                                    else:
                                        set_flash("credito_msg", "warning", f"⚠️ Crédito {prestamo_creado['id']} creado, pero el contrato quedó pendiente: {err_c}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {err_c}")
                            finally:
                                stop_busy()

                with cred_tab2:
                    with st.form("form_credito_express", clear_on_submit=True):
                        cliente_express = st.selectbox(
                            "Cliente",
                            cliente_options,
                            key="cliente_express_credito",
                            format_func=nombre_cliente,
                            index=0
                        )
                        monto_express_new = st.number_input("Monto a prestar", min_value=0.0, step=50000.0, value=300000.0, key="nuevo_monto_express")
                        frecuencia_express_new = st.selectbox("Frecuencia", ["Mensual", "Quincenal"], key="nuevo_frec_express")
                        cuotas_express_new = 5 if frecuencia_express_new == "Mensual" else 6
                        fecha_inicio_express = st.date_input("Fecha de inicio", value=date.today(), key="fecha_inicio_express")
                        st.caption(f"Crédito express a {cuotas_express_new} cuotas de frecuencia {frecuencia_express_new.lower()}.")
                        submit_express = st.form_submit_button("Registrar crédito express", type="primary", disabled=st.session_state.get("app_busy", False))
                    if submit_express:
                        if cliente_express is None:
                            st.warning("ℹ️ Selecciona un cliente para registrar un crédito express.")
                        else:
                            start_busy("Creando crédito express...")
                            try:
                                ok_c, err_c, prestamo_creado = crear_credito_db(cliente_express, monto_express_new, cuotas_express_new, frecuencia_express_new, "Express", fecha_inicio_express)
                                if ok_c:
                                    st.session_state["cliente_express_credito"] = None
                                    if not err_c:
                                        set_flash("credito_msg", "success", f"✅ Crédito {prestamo_creado['id']} creado y contrato enviado correctamente")
                                    else:
                                        set_flash("credito_msg", "warning", f"⚠️ Crédito {prestamo_creado['id']} creado, pero el contrato quedó pendiente: {err_c}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {err_c}")
                            finally:
                                stop_busy()

                with cred_tab3:
                    pendientes_df = estado[estado["estado"] == "Pendiente"].copy()

                    if pendientes_df.empty:
                        st.success("✅ No hay créditos pendientes de envío de contrato.")
                    else:
                        st.caption("Aquí puedes reenviar manualmente el contrato a créditos que ya fueron registrados en el sistema y quedaron pendientes.")
                        pendientes_df = pendientes_df.sort_values(["cliente", "id"])
                        pendientes_options = [None] + pendientes_df["id"].tolist()

                        prestamo_pend_sel = st.selectbox(
                            "Selecciona un crédito pendiente",
                            pendientes_options,
                            index=0,
                            key="sel_credito_pendiente_contrato",
                            format_func=lambda x: "Selecciona un crédito" if x is None else f"{x} — {pendientes_df.loc[pendientes_df['id']==x, 'cliente'].iloc[0]}"
                        )

                        if prestamo_pend_sel is None:
                            st.info("ℹ️ Selecciona un crédito pendiente para enviar el contrato.")
                        else:
                            fila_p = pendientes_df[pendientes_df["id"] == prestamo_pend_sel].iloc[0].to_dict()

                            st.markdown(f"""
                            <div style="border:1px solid #e5e7eb;border-radius:16px;padding:14px 16px;background:#ffffff;margin-bottom:10px;">
                                <div style="font-size:18px;font-weight:800;color:#0f172a;">Crédito {fila_p['id']}</div>
                                <div style="font-size:13px;color:#64748b;margin-top:4px;">{fila_p['cliente']} · {fila_p['tipo']} · Estado: {fila_p['estado']}</div>
                            </div>
                            """, unsafe_allow_html=True)

                            r1, r2, r3, r4 = st.columns(4)
                            r1.metric("Capital", pesos(fila_p["monto_original"]))
                            r2.metric("Cuota", pesos(fila_p["valor_cuota"]))
                            r3.metric("Cuotas", int(fila_p["cuotas"]))
                            r4.metric("Frecuencia", fila_p.get("frecuencia", "Mensual"))

                            contrato_enviado = int(fila_p.get("contrato_enviado", 0) or 0) == 1
                            contrato_aceptado = int(fila_p.get("contrato_aceptado", 0) or 0) == 1
                            desembolso_notificado = int(fila_p.get("desembolso_notificado", 0) or 0) == 1
                            fecha_envio = fila_p.get("fecha_envio_contrato") or "-"
                            fecha_aceptacion = fila_p.get("fecha_aceptacion") or "-"
                            fecha_desembolso = fila_p.get("fecha_desembolso") or "-"

                            st.markdown("### Estado del flujo")
                            f1, f2, f3, f4 = st.columns(4)
                            f1.metric("Contrato enviado", "Sí" if contrato_enviado else "No", fecha_envio if contrato_enviado else None)
                            f2.metric("Esperando aceptación", "Sí" if contrato_enviado and not contrato_aceptado else "No")
                            f3.metric("Contrato aceptado", "Sí" if contrato_aceptado else "No", fecha_aceptacion if contrato_aceptado else None)
                            f4.metric("Desembolso notificado", "Sí" if desembolso_notificado else "No", fecha_desembolso if desembolso_notificado else None)

                            if not contrato_enviado:
                                st.warning("⚠️ Este crédito está pendiente porque aún no se ha enviado el contrato al cliente.")
                            elif contrato_enviado and not contrato_aceptado:
                                st.info("⏳ El contrato ya fue enviado y el sistema está esperando la aceptación del cliente.")
                            elif contrato_aceptado and not desembolso_notificado:
                                st.warning("⚠️ El contrato ya fue aceptado, pero aún no hay confirmación de notificación de desembolso.")
                            else:
                                st.success("✅ El flujo del contrato y desembolso ya quedó completado para este crédito.")

                            if st.button("📨 Enviar contrato manual", type="primary", key="btn_enviar_contrato_manual", disabled=st.session_state.get("app_busy", False)):
                                start_busy("Enviando contrato manual...")
                                try:
                                    ok_send, err_send = enviar_contrato_credito(fila_p)
                                    if ok_send:
                                        set_flash("contrato_msg", "success", f"✅ Contrato enviado correctamente para el crédito {fila_p['id']}. Ahora queda esperando aceptación.")
                                    else:
                                        set_flash("contrato_msg", "warning", f"⚠️ No se pudo enviar el contrato del crédito {fila_p['id']}: {err_send}")
                                    st.rerun()
                                finally:
                                    stop_busy()

                        pendientes_show = pendientes_df[["id", "cliente", "monto_original", "valor_cuota", "cuotas", "frecuencia", "tipo", "estado", "contrato_enviado", "contrato_aceptado", "desembolso_notificado"]].copy()
                        pendientes_show["monto_original"] = pendientes_show["monto_original"].apply(pesos)
                        pendientes_show["valor_cuota"] = pendientes_show["valor_cuota"].apply(pesos)
                        pendientes_show["contrato_enviado"] = pendientes_show["contrato_enviado"].apply(lambda x: "Sí" if int(x or 0) == 1 else "No")
                        pendientes_show["contrato_aceptado"] = pendientes_show["contrato_aceptado"].apply(lambda x: "Sí" if int(x or 0) == 1 else "No")
                        pendientes_show["desembolso_notificado"] = pendientes_show["desembolso_notificado"].apply(lambda x: "Sí" if int(x or 0) == 1 else "No")
                        pendientes_show = pendientes_show.rename(columns={
                            "id": "Crédito",
                            "cliente": "Cliente",
                            "monto_original": "Capital",
                            "valor_cuota": "Cuota",
                            "cuotas": "N.° cuotas",
                            "frecuencia": "Frecuencia",
                            "tipo": "Tipo",
                            "estado": "Estado",
                            "contrato_enviado": "Contrato enviado",
                            "contrato_aceptado": "Aceptado",
                            "desembolso_notificado": "Desembolso notificado"
                        })
                        st.dataframe(pendientes_show, use_container_width=True, hide_index=True)
# ==========================
# 📄 DETALLE
# ==========================
if tab_detalle is not None:
    with tab_detalle:
            st.subheader("📄 Detalle por crédito")
            st.caption("Consulta la ficha del crédito, su plan de cuotas y sus movimientos. Los créditos cerrados se conservan en historial para consulta.")
            show_flash("detalle_msg")

            detalle_activos = estado[(estado["estado"] != "Cancelado") & (pd.to_numeric(estado["saldo"], errors="coerce").fillna(0) > 0)].copy()
            detalle_cerrados = estado[(estado["estado"] == "Cancelado") | (pd.to_numeric(estado["saldo"], errors="coerce").fillna(0) <= 0)].copy()

            det_tab_activos, det_tab_hist = st.tabs(["🟢 Créditos activos", "📚 Historial / cerrados"])

            def render_detalle_creditos(df_detalle: pd.DataFrame, empty_msg: str):
                if df_detalle.empty:
                    st.info(empty_msg)
                    return

                for _, row in df_detalle.iterrows():
                    with st.expander(f"💳 Préstamo {row['id']} — {row['cliente']}"):
                        estado_contrato = "Aceptado" if int(row.get("contrato_aceptado", 0) or 0) == 1 else "Pendiente"
                        st.markdown(f"""
                        <div style="border:1px solid #e5e7eb;border-radius:16px;padding:14px 16px;background:#ffffff;margin-bottom:10px;">
                            <div style="font-size:18px;font-weight:800;color:#0f172a;">Crédito {row['id']}</div>
                            <div style="font-size:13px;color:#64748b;margin-top:4px;">{row['cliente']} · {row['tipo']} · {row['estado']} · Frecuencia: {row.get('frecuencia', 'Mensual')} · Contrato: {estado_contrato}</div>
                        </div>
                        """, unsafe_allow_html=True)

                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("💰 Total crédito", pesos(row["monto_total_credito"]))
                        c2.metric("✅ Pagado", pesos(row["total_pagado"]))
                        c3.metric("🏦 Saldo capital", pesos(row["saldo_capital"]))
                        c4.metric("⏳ Saldo pendiente", pesos(row["saldo"]))
                        c5, c6, c7 = st.columns(3)
                        c5.metric("💳 Cuota actual", pesos(row["valor_cuota"]))
                        c6.metric("📆 N.° cuotas", int(row["cuotas"]))
                        c7.metric("📊 Tasa mensual", f"{float(row['tasa_mensual'] or 0):.4f}")

                        with get_conn() as conn:
                            cuotas_credito = pd.read_sql(text("""
                                SELECT nro_cuota, fecha_vencimiento, valor_cuota, estado
                                FROM cuotas
                                WHERE prestamo_id = :id
                                ORDER BY nro_cuota ASC
                            """), conn, params={"id": row["id"]})
                            pagos_credito = pd.read_sql(text("""
                                SELECT fecha_pago, valor, tipo_movimiento, detalle
                                FROM pagos
                                WHERE prestamo_id = :id
                                ORDER BY id_pago DESC
                            """), conn, params={"id": row["id"]})

                        t1, t2 = st.tabs(["📅 Cuotas del crédito", "💸 Movimientos registrados"])
                        with t1:
                            if cuotas_credito.empty:
                                st.info("Sin cuotas registradas para este crédito.")
                            else:
                                cuotas_credito["valor_cuota"] = cuotas_credito["valor_cuota"].apply(pesos)
                                cuotas_credito = cuotas_credito.rename(columns={
                                    "nro_cuota": "Cuota",
                                    "fecha_vencimiento": "Fecha de vencimiento",
                                    "valor_cuota": "Valor cuota",
                                    "estado": "Estado"
                                })
                                st.dataframe(cuotas_credito, use_container_width=True, hide_index=True)
                        with t2:
                            if pagos_credito.empty:
                                st.info("Sin movimientos registrados para este crédito.")
                            else:
                                pagos_credito["valor"] = pagos_credito["valor"].apply(pesos)
                                pagos_credito = pagos_credito.rename(columns={
                                    "fecha_pago": "Fecha movimiento",
                                    "valor": "Valor",
                                    "tipo_movimiento": "Tipo",
                                    "detalle": "Detalle"
                                })
                                st.dataframe(pagos_credito, use_container_width=True, hide_index=True)

            with det_tab_activos:
                render_detalle_creditos(detalle_activos, "ℹ️ No hay créditos activos con saldo pendiente.")
            with det_tab_hist:
                render_detalle_creditos(detalle_cerrados, "ℹ️ No hay créditos cerrados o históricos para mostrar.")
# ==========================
# 💰 PAGOS
# ==========================
if "pago_msg" not in st.session_state:
    st.session_state.pago_msg = None
if "reset_select_prestamo_pago" not in st.session_state:
    st.session_state.reset_select_prestamo_pago = False
if tab_pagos is not None:
    with tab_pagos:
            st.subheader("💰 Pagos del crédito")
            st.caption("Aquí solo se muestran créditos activos con saldo pendiente. Los créditos cerrados siguen visibles en Resumen e Historial, pero no interfieren en la operación diaria.")
            activos = estado[(estado["estado"] != "Cancelado") & (pd.to_numeric(estado["saldo"], errors="coerce").fillna(0) > 0)].copy()
            if activos.empty:
                st.info("ℹ️ No hay préstamos activos con saldo pendiente.")
            else:
                opciones = {f"{r.id} — {r.cliente}": r for r in activos.itertuples()}
                opciones_lista = [None] + list(opciones.keys())
                if st.session_state.get("reset_select_prestamo_pago", False):
                    if "select_prestamo_pago" in st.session_state:
                        del st.session_state["select_prestamo_pago"]
                    st.session_state.reset_select_prestamo_pago = False
                seleccion = st.selectbox(
                    "📌 Préstamo",
                    opciones_lista,
                    index=0,
                    format_func=lambda x: "Selecciona un crédito" if x is None else x,
                    key="select_prestamo_pago"
                )

                if seleccion is None:
                    st.info("ℹ️ Selecciona un crédito para ver su información y registrar el movimiento.")
                else:
                    prestamo = opciones[seleccion]
                    with get_conn() as conn:
                        proxima_cuota = obtener_proxima_cuota(conn, prestamo.id)
                    info1, info2, info3, info4 = st.columns(4)
                    info1.metric("💳 Cuota actual", pesos(prestamo.valor_cuota))
                    info2.metric("🏦 Saldo capital", pesos(prestamo.saldo_capital))
                    info3.metric("⏳ Saldo cuotas", pesos(prestamo.saldo))
                    info4.metric("📊 Tasa mensual", f"{float(prestamo.tasa_mensual or 0):.4f}")
                    st.divider()
                    tab_pago_cuota, tab_abono_capital = st.tabs(["✅ Pago de cuota", "🏦 Abono a capital"])

                    with tab_pago_cuota:
                        if not proxima_cuota:
                            st.info("ℹ️ Este crédito no tiene cuotas pendientes.")
                        else:
                            st.markdown(f"""
                            <div style='padding:14px 16px;border:1px solid #e5e7eb;border-radius:16px;background:#f8fafc;margin-bottom:12px;'>
                                <div style='font-size:13px;color:#64748b;margin-bottom:6px;'>Próxima cuota pendiente</div>
                                <div style='font-size:18px;font-weight:800;color:#0f172a;'>Cuota #{proxima_cuota[1]} — {pesos(proxima_cuota[2])}</div>
                                <div style='font-size:13px;color:#475569;margin-top:4px;'>Fecha de vencimiento: {proxima_cuota[3]}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            with st.form("form_pago_cuota", clear_on_submit=True):
                                fecha_pago = st.date_input("📅 Fecha de movimiento", value=date.today(), key="fecha_movimiento_pago")
                                submit_pago_cuota = st.form_submit_button("Registrar pago de cuota", type="primary", disabled=st.session_state.get("app_busy", False))
                            if submit_pago_cuota:
                                start_busy("Aplicando pago de cuota...")
                                try:
                                    with st.spinner("⏳ Aplicando pago, por favor espera..."):
                                        resultado = registrar_pago_cuota(prestamo.id, fecha_pago)
                                        if resultado.get("ok"):
                                            st.session_state.pago_msg = {"tipo": "CUOTA", **resultado}
                                            st.session_state.reset_select_prestamo_pago = True
                                            time.sleep(0.2)
                                            st.rerun()
                                        else:
                                            st.error(f"❌ {resultado.get('error')}")
                                finally:
                                    stop_busy()

                    with tab_abono_capital:
                        st.caption("El abono a capital reduce el saldo del préstamo y recalcula el valor de las cuotas pendientes, manteniendo el número de cuotas restantes.")
                        with st.form("form_abono_capital", clear_on_submit=True):
                            fecha_pago = st.date_input("📅 Fecha de movimiento", value=date.today(), key="fecha_movimiento_abono")
                            abono_capital = st.number_input(
                                "Valor abono a capital",
                                min_value=0.0,
                                step=1000.0,
                                value=0.0,
                                key="abono_capital"
                            )
                            submit_abono_capital = st.form_submit_button("Aplicar abono a capital", disabled=st.session_state.get("app_busy", False))
                        if submit_abono_capital:
                            start_busy("Aplicando abono a capital...")
                            try:
                                with st.spinner("⏳ Aplicando abono a capital..."):
                                    resultado = registrar_abono_capital(prestamo.id, fecha_pago, abono_capital)
                                    if resultado.get("ok"):
                                        st.session_state.pago_msg = {"tipo": "ABONO_CAPITAL", **resultado}
                                        st.session_state.reset_select_prestamo_pago = True
                                        time.sleep(0.2)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {resultado.get('error')}")
                            finally:
                                stop_busy()
            if st.session_state.pago_msg:
                m = st.session_state.pago_msg
                if m["tipo"] == "CUOTA":
                    if m.get("tiene_correo") and m.get("correo"):
                        st.success(f"✅ Pago de cuota registrado y correo enviado - Crédito {m['credito']} | Cuota #{m['cuota']}")
                    elif m.get("tiene_correo") and not m.get("correo"):
                        st.warning(f"⚠️ Pago de cuota registrado, pero el correo no se pudo enviar - Crédito {m['credito']}")
                        if m.get("correo_error"):
                            st.error(f"Detalle correo: {m['correo_error']}")
                    else:
                        st.success(f"✅ Pago de cuota registrado - Crédito {m['credito']}")
                if m["tipo"] == "ABONO_CAPITAL":
                    if m.get("tiene_correo") and m.get("correo"):
                        st.success(f"✅ Abono a capital registrado y correo enviado - Crédito {m['credito']} | Nueva cuota: {pesos(m['nueva_cuota'])}")
                    elif m.get("tiene_correo") and not m.get("correo"):
                        st.warning(f"⚠️ Abono a capital registrado, pero el correo no se pudo enviar - Crédito {m['credito']}")
                        if m.get("correo_error"):
                            st.error(f"Detalle correo: {m['correo_error']}")
                    else:
                        st.success(f"✅ Abono a capital registrado - Crédito {m['credito']}")
                st.session_state.pago_msg = None
# ==========================
# 🧮 SIMULADOR
# ==========================
if tab_sim is not None:
    with tab_sim:
            st.subheader("🧮 Simulador de crédito")
            t1, t2 = st.tabs([
                "💳 Crédito normal",
                "⚡ Crédito express"
            ])
            # --------------------------
            # 💳 CRÉDITO NORMAL
            # --------------------------
            with t1:
                st.markdown("### 💳 Crédito normal")
                monto_normal = st.number_input(
                    "Monto del crédito",
                    min_value=100_000,
                    step=100_000,
                    value=1_000_000,
                    key="monto_normal"
                )
                cuotas_normal = st.selectbox(
                    "Número de cuotas",
                    [12, 15],
                    key="cuotas_normal"
                )
                if st.button("Calcular crédito normal"):
                    cuota = calcular_cuota_normal(monto_normal, cuotas_normal)
                    st.success(
                        f"📌 Cuota mensual: **{pesos(cuota)}**\n\n"
                        f"📆 Total cuotas: **{cuotas_normal}**\n\n"
                        f"💰 Total a pagar: **{pesos(cuota * cuotas_normal)}**"
                    )
            # --------------------------
            # ⚡ CRÉDITO EXPRESS
            # --------------------------
            with t2:
                st.markdown("### ⚡ Crédito express")
                monto_express = st.number_input(
                    "Monto del crédito express",
                    min_value=50_000,
                    step=50_000,
                    value=200_000,
                    key="monto_express"
                )
                frecuencia = st.selectbox(
                    "Frecuencia de pago",
                    ["Mensual", "Quincenal"],
                    key="frecuencia_express"
                )
                cuotas_express = 5 if frecuencia == "Mensual" else 6
                if st.button("Calcular crédito express"):
                    cuota = calcular_cuota_express(
                        monto_express,
                        cuotas_express,
                        frecuencia
                    )
                    st.success(
                        f"📌 Cuota {frecuencia.lower()}: **{pesos(cuota)}**\n\n"
                        f"📆 Total cuotas: **{cuotas_express}**\n\n"
                        f"💰 Total a pagar estimado: **{pesos(cuota * cuotas_express)}**\n\n"
                        f"💰 Total a pagar estimado: **{pesos(cuota * cuotas_express)}**\n\n"
                        f"📈 Tasa aplicada: **{calcular_tasa_express(frecuencia)*100:.2f}%**"
                    )





