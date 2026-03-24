import streamlit as st
import pandas as pd
import os
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
# Aquí Python va y busca la dirección mágica en tu archivo secrets.toml o en Render
DATABASE_URL = st.secrets["DATABASE_URL"]
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
    st.title("🔐 Acceso al sistema")
    usuario = st.text_input("Usuario")
    clave = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
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
    st.stop()
# ==========================
# HEADER - TITULO
# ==========================
col1, col2, col3 = st.columns([1,4,1])
with col2:
    st.image("logo_creddt.png", width=90)
    st.markdown("""
    <h1 style='text-align:center;margin-bottom:0;'>CREDDT | CRNTECH</h1>
    <p style='text-align:center;color:#666;'>Plataforma inteligente de gestión de créditos</p>
    """, unsafe_allow_html=True)
st.divider()
# ==========================
# VARIABLES SEGURAS
# ==========================
MAILERSEND_API_KEY = st.secrets["MAILERSEND_API_KEY"]
MAILERSEND_FROM_EMAIL = st.secrets["MAILERSEND_FROM_EMAIL"]
MAILERSEND_FROM_NAME = st.secrets.get("MAILERSEND_FROM_NAME", "CREDDT CRNTECH")
APP_BASE_URL = st.secrets.get("APP_BASE_URL", "").rstrip("/")
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
                fecha_inicio = COALESCE(fecha_inicio, CURRENT_DATE::text),
                frecuencia = COALESCE(frecuencia, 'Mensual')
            WHERE saldo_capital IS NULL
               OR tasa_mensual IS NULL
               OR contrato_aceptado IS NULL
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
def construir_cuerpo_correo(tipo, nombre_cliente, **kwargs):
    if tipo == "RECIBO_CUOTA":
        return f"""Estimado(a) {nombre_cliente},
Reciba un cordial saludo.
Le confirmamos que el pago de su cuota fue registrado exitosamente en nuestro sistema.
Información del movimiento:
- Crédito: {kwargs.get('prestamo_id')}
- Cuota aplicada: {kwargs.get('cuota_nro')}
- Fecha de pago: {kwargs.get('fecha_pago')}
- Valor pagado: {pesos(kwargs.get('valor'))}
Adjunto encontrará el comprobante correspondiente para su soporte.
Cordialmente,
CREDDT CRNTECH
Área Administrativa y Financiera
"""
    if tipo == "RECIBO_ABONO":
        return f"""Estimado(a) {nombre_cliente},
Reciba un cordial saludo.
Le confirmamos que su abono a capital fue registrado exitosamente.
Información del movimiento:
- Crédito: {kwargs.get('prestamo_id')}
- Fecha de abono: {kwargs.get('fecha_pago')}
- Abono a capital: {pesos(kwargs.get('valor'))}
- Nuevo saldo capital: {pesos(kwargs.get('saldo_capital'))}
- Nueva cuota estimada: {pesos(kwargs.get('nueva_cuota'))}
Adjunto encontrará el comprobante correspondiente para su soporte.
Cordialmente,
CREDDT CRNTECH
Área Administrativa y Financiera
"""
    if tipo == "CONTRATO":
        return f"""Estimado(a) {nombre_cliente},
Reciba un cordial saludo.
Adjunto encontrará el contrato correspondiente a su crédito para consulta y soporte.
Información base del crédito:
- Crédito: {kwargs.get('prestamo_id')}
- Monto aprobado: {pesos(kwargs.get('monto'))}
- Número de cuotas: {kwargs.get('cuotas')}
- Valor cuota actual: {pesos(kwargs.get('valor_cuota'))}
Cordialmente,
CREDDT CRNTECH
Área Administrativa y Financiera
"""
    if tipo == "RECORDATORIO":
        return f"""Estimado(a) {nombre_cliente},
Reciba un cordial saludo.
Le recordamos que tiene una cuota pendiente asociada a su crédito.
Información del recordatorio:
- Crédito: {kwargs.get('prestamo_id')}
- Cuota pendiente: {kwargs.get('cuota_nro')}
- Fecha de vencimiento: {kwargs.get('fecha_vencimiento')}
- Valor a pagar: {pesos(kwargs.get('valor'))}
Agradecemos realizar el pago oportunamente para mantener su crédito al día.
Cordialmente,
CREDDT CRNTECH
Área Administrativa y Financiera
"""
    if tipo == "DESEMBOLSO":
        return f"""Estimado(a) {nombre_cliente},
Reciba un cordial saludo.
Le informamos que su contrato fue aceptado correctamente y su crédito quedó activo para proceso de desembolso.
Información del crédito:
- Crédito: {kwargs.get('prestamo_id')}
- Tipo: {kwargs.get('tipo')}
- Monto aprobado: {pesos(kwargs.get('monto'))}
- Frecuencia: {kwargs.get('frecuencia')}
- Cuotas: {kwargs.get('cuotas')}
- Valor cuota: {pesos(kwargs.get('valor_cuota'))}
Cordialmente,
CREDDT CRNTECH
Área Administrativa y Financiera
"""
    return f"""Estimado(a) {nombre_cliente},
Reciba un cordial saludo de CREDDT CRNTECH.
Adjunto encontrará la información correspondiente a su crédito.
Cordialmente,
CREDDT CRNTECH
Área Administrativa y Financiera
"""
def calcular_cuotas_pagadas(total_pagado, valor_cuota):
    if valor_cuota <= 0:
        return 0
    return int(total_pagado // valor_cuota)
def generar_recibo_pdf(prestamo_id, cliente, monto_credito, fecha_pago, valor_pagado, titulo="RECIBO DE PAGO", subtitulo="VALOR PAGADO"):
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    )
    from reportlab.lib import colors, pagesizes
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import Image
    import os
    ruta_pdf = os.path.join(tempfile.gettempdir(), f"recibo_{prestamo_id}.pdf")
    doc = SimpleDocTemplate(
        ruta_pdf,
        pagesize=pagesizes.A4,
        rightMargin=60,
        leftMargin=60,
        topMargin=60,
        bottomMargin=50
    )
    elementos = []
    estilos = getSampleStyleSheet()
    azul = colors.HexColor("#1E3A8A")
    gris = colors.HexColor("#64748B")
    # ==========================
    # LOGO (opcional)
    # ==========================
    logo_path = "logo_creddt.png"
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.3*inch, height=1.1*inch)
        logo.hAlign = 'CENTER'
        elementos.append(logo)
        elementos.append(Spacer(1, 15))
    # ==========================
    # MARCA + SLOGAN
    # ==========================
    estilo_marca = ParagraphStyle(
        name='Marca',
        parent=estilos['Normal'],
        alignment=TA_CENTER,
        fontSize=14,
        textColor=colors.black,
        spaceAfter=4
    )
    estilo_slogan = ParagraphStyle(
        name='Slogan',
        parent=estilos['Normal'],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=gris,
        spaceAfter=20
    )
    elementos.append(Paragraph("<b>CREDDT CRNTECH APPLICATION</b>", estilo_marca))
    elementos.append(Paragraph("Tu crédito, tu ritmo.", estilo_slogan))
    # Línea fina elegante
    elementos.append(HRFlowable(width="60%", thickness=1, color=colors.lightgrey))
    elementos.append(Spacer(1, 25))
    # ==========================
    # TÍTULO
    # ==========================
    estilo_titulo = ParagraphStyle(
        name='Titulo',
        parent=estilos['Heading1'],
        alignment=TA_CENTER,
        fontSize=18,
        textColor=azul,
        spaceAfter=25
    )
    elementos.append(Paragraph(titulo, estilo_titulo))
    # ==========================
    # DATOS
    # ==========================
    estilo_label = ParagraphStyle(
        name='Label',
        parent=estilos['Normal'],
        fontSize=11,
        textColor=gris,
        spaceAfter=6
    )
    estilo_valor = ParagraphStyle(
        name='Valor',
        parent=estilos['Normal'],
        fontSize=12,
        textColor=colors.black,
        spaceAfter=12
    )
    elementos.append(Paragraph("Préstamo ID", estilo_label))
    elementos.append(Paragraph(f"<b>{prestamo_id}</b>", estilo_valor))
    elementos.append(Paragraph("Cliente", estilo_label))
    elementos.append(Paragraph(f"<b>{cliente}</b>", estilo_valor))
    elementos.append(Paragraph("Fecha de pago", estilo_label))
    elementos.append(Paragraph(f"{fecha_pago}", estilo_valor))
    elementos.append(Paragraph("Monto original", estilo_label))
    elementos.append(Paragraph(f"$ {monto_credito:,.0f}", estilo_valor))
    elementos.append(Spacer(1, 25))
    # ==========================
    # VALOR DESTACADO
    # ==========================
    elementos.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    elementos.append(Spacer(1, 20))
    estilo_pago = ParagraphStyle(
        name='PagoGrande',
        parent=estilos['Normal'],
        alignment=TA_CENTER,
        fontSize=28,
        textColor=azul,
        spaceAfter=5
    )
    estilo_pago_label = ParagraphStyle(
        name='PagoLabel',
        parent=estilos['Normal'],
        alignment=TA_CENTER,
        fontSize=11,
        textColor=gris
    )
    elementos.append(Paragraph(subtitulo, estilo_pago_label))
    elementos.append(Spacer(1, 5))
    elementos.append(Paragraph(f"<b>$ {valor_pagado:,.0f}</b>", estilo_pago))
    elementos.append(Spacer(1, 40))
    # ==========================
    # FOOTER
    # ==========================
    elementos.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    elementos.append(Spacer(1, 10))
    estilo_footer = ParagraphStyle(
        name='Footer',
        parent=estilos['Normal'],
        alignment=TA_CENTER,
        fontSize=9,
        textColor=gris
    )
    elementos.append(Paragraph(
        "Este documento es un comprobante oficial generado automáticamente.",
        estilo_footer
    ))
    elementos.append(Spacer(1, 5))
    elementos.append(Paragraph(
        "CREDDT CRNTECH APPLICATION • Cali - Colombia • creddtcrntechapplication@gmail.com",
        estilo_footer
    ))
    # ✅ GENERAR PDF
    doc.build(elementos)
    return ruta_pdf
def generar_contrato_pdf(prestamo_id, cliente, monto_credito, cuotas, valor_cuota, tipo_credito, fecha_emision=None):
    ruta_pdf = os.path.join(tempfile.gettempdir(), f"contrato_{prestamo_id}.pdf")
    fecha_emision = fecha_emision or date.today().isoformat()
    doc = SimpleDocTemplate(
        ruta_pdf,
        pagesize=pagesizes.A4,
        rightMargin=55,
        leftMargin=55,
        topMargin=55,
        bottomMargin=45
    )
    estilos = getSampleStyleSheet()
    elementos = []
    azul = colors.HexColor("#1E3A8A")
    gris = colors.HexColor("#64748B")
    estilo_titulo = ParagraphStyle(
        name='TituloContrato',
        parent=estilos['Heading1'],
        alignment=TA_CENTER,
        fontSize=18,
        textColor=azul,
        spaceAfter=20
    )
    estilo_normal = ParagraphStyle(
        name='ContratoNormal',
        parent=estilos['Normal'],
        fontSize=10.5,
        leading=15,
        textColor=colors.black,
        spaceAfter=10
    )
    estilo_footer = ParagraphStyle(
        name='ContratoFooter',
        parent=estilos['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=gris
    )
    if os.path.exists("logo_creddt.png"):
        logo = Image("logo_creddt.png", width=2.2*inch, height=1.0*inch)
        logo.hAlign = 'CENTER'
        elementos.append(logo)
        elementos.append(Spacer(1, 12))
    elementos.append(Paragraph("CONTRATO DE CRÉDITO", estilo_titulo))
    elementos.append(Paragraph(f"Fecha de emisión: <b>{fecha_emision}</b>", estilo_normal))
    elementos.append(Paragraph(
        f"Cliente: <b>{cliente}</b><br/>"
        f"Crédito: <b>{prestamo_id}</b><br/>"
        f"Tipo de crédito: <b>{tipo_credito}</b><br/>"
        f"Monto aprobado: <b>{pesos(monto_credito)}</b><br/>"
        f"Número de cuotas: <b>{cuotas}</b><br/>"
        f"Valor cuota actual: <b>{pesos(valor_cuota)}</b>",
        estilo_normal
    ))
    elementos.append(Paragraph(
        "El presente documento deja constancia de las condiciones generales del crédito aprobado por CREDDT CRNTECH. "
        "El cliente se compromete a realizar los pagos de sus cuotas en las fechas establecidas y a mantener actualizada "
        "su información de contacto para notificaciones, recibos y recordatorios.",
        estilo_normal
    ))
    elementos.append(Paragraph(
        "Los abonos extraordinarios a capital, cuando sean aceptados y registrados, reducirán el saldo del crédito y "
        "permitirán recalcular el valor de las cuotas pendientes, manteniendo la cantidad de cuotas restantes.",
        estilo_normal
    ))
    elementos.append(Spacer(1, 25))
    elementos.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    elementos.append(Spacer(1, 18))
    elementos.append(Paragraph("CREDDT CRNTECH • Documento generado automáticamente para soporte del crédito.", estilo_footer))
    doc.build(elementos)
    return ruta_pdf
def obtener_datos_cliente(conn, cedula):
    return conn.execute(text("""
        SELECT nombres || ' ' || apellidos AS nombre, correo
        FROM clientes
        WHERE cedula = :cedula
    """), {"cedula": cedula}).fetchone()
def enviar_pdf_por_correo(destino, asunto, cuerpo, ruta_pdf, nombre_adj):
    with open(ruta_pdf, "rb") as f:
        return enviar_correo_async(
            destino=destino,
            asunto=asunto,
            cuerpo=cuerpo,
            attachment_bytes=f.read(),
            attachment_name=nombre_adj
        )
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
        ruta_pdf = generar_contrato_pdf(
            prestamo_row["id"],
            prestamo_row["cliente"],
            prestamo_row["monto_original"],
            prestamo_row["cuotas"],
            prestamo_row["valor_cuota"],
            prestamo_row["tipo"]
        )
        cuerpo = construir_cuerpo_correo(
            "CONTRATO",
            prestamo_row["cliente"],
            prestamo_id=prestamo_row["id"],
            monto=prestamo_row["monto_original"],
            cuotas=prestamo_row["cuotas"],
            valor_cuota=prestamo_row["valor_cuota"]
        )
        html_boton = None
        if enlace:
            cuerpo_html = cuerpo.replace("\n", "<br>")
            html_boton = f"""
            <div style="font-family: Arial, Helvetica, sans-serif; background-color: #f4f6f8; padding: 30px;">
                <div style="max-width: 680px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb;">
                    <div style="background: #0f172a; padding: 24px 30px;">
                        <h2 style="margin: 0; color: #ffffff; font-size: 22px;">CREDDT CRNTECH</h2>
                        <p style="margin: 8px 0 0 0; color: #cbd5e1; font-size: 14px;">Aceptación de contrato</p>
                    </div>
                    <div style="padding: 30px; color: #1f2937; font-size: 15px; line-height: 1.7;">
                        {cuerpo_html}<br><br>
                        <div style="text-align:center; margin: 28px 0;">
                            <a href="{enlace}" style="background:#0f172a; color:#ffffff; padding:14px 24px; border-radius:8px; text-decoration:none; font-weight:700; display:inline-block;">Aceptar contrato</a>
                        </div>
                        <p style="font-size:13px; color:#64748b;">Si el botón no abre, copie y pegue este enlace en su navegador:<br>{enlace}</p>
                    </div>
                </div>
            </div>
            """
        with open(ruta_pdf, "rb") as f:
            return enviar_correo_async(
                prestamo_row["correo"],
                f"Contrato crédito {prestamo_row['id']}",
                cuerpo,
                attachment_bytes=f.read(),
                attachment_name=f"contrato_{prestamo_row['id']}.pdf",
                html_override=html_boton
            )
    finally:
        if ruta_pdf and os.path.exists(ruta_pdf):
            try:
                os.remove(ruta_pdf)
            except Exception:
                pass
def enviar_correo_desembolso_credito(prestamo_row):
    if not prestamo_row.get("correo"):
        return False, "Cliente sin correo registrado"
    cuerpo = construir_cuerpo_correo(
        "DESEMBOLSO",
        prestamo_row["cliente"],
        prestamo_id=prestamo_row["id"],
        tipo=prestamo_row["tipo"],
        monto=prestamo_row["monto_original"],
        frecuencia=prestamo_row.get("frecuencia", "Mensual"),
        cuotas=prestamo_row["cuotas"],
        valor_cuota=prestamo_row["valor_cuota"]
    )
    return enviar_correo_async(prestamo_row["correo"], f"Crédito {prestamo_row['id']} aprobado para desembolso", cuerpo)
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
            return True, "El contrato ya había sido aceptado previamente", dict(prestamo)
        conn.execute(text("""
            UPDATE prestamos
            SET contrato_aceptado = 1, estado = 'Activo', fecha_aceptacion = :fecha, fecha_desembolso = :fecha
            WHERE id = :id
        """), {"fecha": datetime.now().isoformat(timespec='seconds'), "id": prestamo["id"]})
        conn.commit()
    prestamo_row = dict(prestamo)
    enviar_correo_desembolso_credito(prestamo_row)
    return True, "Contrato aceptado correctamente", prestamo_row
def procesar_recordatorios_automaticos():
    enviados = 0
    with get_conn() as conn:
        rows = conn.execute(text("""
            SELECT cu.id_cuota, cu.prestamo_id, cu.nro_cuota, cu.fecha_vencimiento::date AS fecha_vencimiento, cu.valor_cuota,
                   c.nombres || ' ' || c.apellidos AS cliente, c.correo
            FROM cuotas cu
            JOIN prestamos p ON p.id = cu.prestamo_id
            JOIN clientes c ON c.cedula = p.cliente_cedula
            WHERE cu.estado IN ('Pendiente', 'Parcial')
              AND c.correo IS NOT NULL
              AND cu.fecha_vencimiento::date BETWEEN CURRENT_DATE - INTERVAL '1 day' AND CURRENT_DATE + INTERVAL '3 day'
        """)).mappings().all()
        for r in rows:
            dias = (r['fecha_vencimiento'] - date.today()).days
            tipo_r = f"D{dias}"
            ya = conn.execute(text("SELECT COUNT(*) FROM reminders_sent WHERE id_cuota = :id_cuota AND tipo_recordatorio = :tipo"), {"id_cuota": r['id_cuota'], "tipo": tipo_r}).scalar()
            if int(ya or 0) > 0:
                continue
            cuerpo = construir_cuerpo_correo('RECORDATORIO', r['cliente'], prestamo_id=r['prestamo_id'], cuota_nro=r['nro_cuota'], fecha_vencimiento=r['fecha_vencimiento'], valor=r['valor_cuota'])
            ok, _ = enviar_correo_async(r['correo'], f"Recordatorio de pago crédito {r['prestamo_id']}", cuerpo)
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
    if st.button("✅ Aceptar contrato", type="primary"):
        ok, mensaje, _ = aceptar_contrato_por_token(token)
        if ok:
            st.success(mensaje)
        else:
            st.error(mensaje)
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
                f"Recibo pago {prestamo_id}",
                cuerpo,
                pdf,
                f"recibo_{prestamo_id}.pdf"
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
def enviar_correo_mailersend(
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
                    <p style="margin: 8px 0 0 0; color: #cbd5e1; font-size: 14px;">Confirmación de pago</p>
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
            "from": {
                "email": MAILERSEND_FROM_EMAIL,
                "name": MAILERSEND_FROM_NAME
            },
            "to": [
                {
                    "email": destino,
                    "name": destino
                }
            ],
            "subject": asunto,
            "text": cuerpo,
            "html": html_override or html_template
        }
        if attachment_bytes:
            payload["attachments"] = [
                {
                    "filename": attachment_name or "recibo.pdf",
                    "content": base64.b64encode(attachment_bytes).decode("utf-8"),
                    "disposition": "attachment"
                }
            ]
        headers = {
            "Authorization": f"Bearer {MAILERSEND_API_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.post(
            "https://api.mailersend.com/v1/email",
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
        return False, f"MailerSend {response.status_code}: {detalle}"
    except requests.Timeout:
        return False, "Timeout conectando con MailerSend"
    except requests.RequestException as e:
        return False, f"Error de red con MailerSend: {e}"
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
    return enviar_correo_mailersend(
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
            p.cliente_cedula, p.contrato_aceptado, p.saldo_capital, p.tasa_mensual, c.nombres, c.apellidos, c.correo
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
tab_resumen, tab_clientes, tab_creditos, tab_detalle, tab_pagos, tab_sim = st.tabs([
    "📊 Resumen",
    "👥 Clientes",
    "🆕 Nuevo crédito",
    "📄 Detalle por crédito",
    "💰 Pagos",
    "🧮 Simulador"
])
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
    st.divider()
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
    st.divider()
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
    st.divider()
    st.subheader("🔎 Consulta mensual (corte 02 → 02)")
    mes_consulta = st.selectbox(
        "Selecciona el mes",
        pd.date_range("2025-12-01", "2030-12-01", freq="MS").strftime("%Y-%m")
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
with tab_clientes:
    st.subheader("👥 Gestión de clientes")

    show_flash("clientes_msg")

    with get_conn() as conn:
        clientes_df = pd.read_sql(text("SELECT cedula, nombres, apellidos, ciudad, telefono, correo, direccion, empresa, fecha_nacimiento, cargo FROM clientes ORDER BY nombres, apellidos"), conn)

    c1, c2 = st.columns([1.05, 0.95])

    with c1:
        st.markdown("### Registrar cliente")
        with st.form("form_nuevo_cliente", clear_on_submit=True):
            cedula_new = st.text_input("Cédula *")
            nombres_new = st.text_input("Nombres *")
            apellidos_new = st.text_input("Apellidos *")
            ciudad_new = st.text_input("Ciudad")
            telefono_new = st.text_input("Teléfono")
            correo_new = st.text_input("Correo")
            direccion_new = st.text_input("Dirección")
            empresa_new = st.text_input("Empresa")
            fecha_nacimiento_new = st.date_input("Fecha de nacimiento", value=None, format="YYYY-MM-DD")
            cargo_new = st.text_input("Cargo")
            guardar_cliente = st.form_submit_button("Guardar cliente", type="primary")
            if guardar_cliente:
                if not cedula_new.strip() or not nombres_new.strip() or not apellidos_new.strip():
                    st.error("❌ Cédula, nombres y apellidos son obligatorios")
                else:
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

    with c2:
        st.markdown("### Gestión de cliente")
        if clientes_df.empty:
            st.info("No hay clientes registrados.")
        else:
            clientes_df = clientes_df.fillna("")
            cliente_sel = st.selectbox(
                "Selecciona un cliente",
                clientes_df["cedula"].tolist(),
                format_func=lambda x: f"{x} — {clientes_df.loc[clientes_df['cedula']==x, 'nombres'].iloc[0]} {clientes_df.loc[clientes_df['cedula']==x, 'apellidos'].iloc[0]}",
                key="sel_cliente_gestion"
            )
            fila = clientes_df[clientes_df["cedula"] == cliente_sel].iloc[0]

            with st.expander("✏️ Editar cliente", expanded=False):
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
                        format="YYYY-MM-DD",
                        key="fecha_nacimiento_edit"
                    )
                    cargo_edit = st.text_input("Cargo", value=fila["cargo"])
                    actualizar = st.form_submit_button("Guardar cambios", type="primary")
                    if actualizar:
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
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ No se pudo actualizar el cliente: {e}")

            with st.expander("🗑️ Borrar cliente", expanded=False):
                st.warning("Esta acción eliminará el cliente solo si no tiene créditos asociados.")
                if st.button("Borrar cliente seleccionado", key="btn_borrar_cliente", type="secondary"):
                    ok_del, err_del = eliminar_cliente_db(cliente_sel)
                    if ok_del:
                        set_flash("clientes_msg", "success", "✅ Cliente eliminado correctamente")
                        st.rerun()
                    else:
                        st.error(f"❌ {err_del}")

    st.divider()
    with st.expander("📋 Ver base de clientes", expanded=False):
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
with tab_creditos:
    st.subheader("🆕 Registrar nuevo crédito")
    show_flash("credito_msg")
    with get_conn() as conn:
        clientes_credito_df = pd.read_sql(text("SELECT cedula, nombres, apellidos, correo FROM clientes ORDER BY nombres, apellidos"), conn)
    if clientes_credito_df.empty:
        st.info("ℹ️ Primero registra un cliente para crear créditos.")
    else:
        tcred1, tcred2 = st.tabs(["💳 Crédito normal", "⚡ Crédito express"])
        with tcred1:
            cliente_normal = st.selectbox(
                "Cliente",
                clientes_credito_df["cedula"].tolist(),
                key="cliente_normal_credito",
                format_func=lambda x: f"{x} — {clientes_credito_df.loc[clientes_credito_df['cedula']==x, 'nombres'].iloc[0]} {clientes_credito_df.loc[clientes_credito_df['cedula']==x, 'apellidos'].iloc[0]}"
            )
            monto_normal_new = st.number_input("Monto a prestar", min_value=0.0, step=100000.0, value=1000000.0, key="nuevo_monto_normal")
            cuotas_normal_new = st.selectbox("Número de cuotas", [12, 15], key="nuevo_cuotas_normal")
            frecuencia_normal_new = st.selectbox("Frecuencia", ["Mensual", "Quincenal"], key="nuevo_frec_normal")
            fecha_inicio_normal = st.date_input("Fecha de inicio", value=date.today(), key="fecha_inicio_normal")
            cuota_preview = calcular_cuota_normal(monto_normal_new, cuotas_normal_new, frecuencia_normal_new)
            st.info(f"Cuota estimada: {pesos(cuota_preview)} | Tasa normal: {calcular_tasa_normal(cuotas_normal_new)*100:.2f}%")
            if st.button("Registrar crédito normal", type="primary", key="btn_crear_normal"):
                ok_c, err_c, prestamo_creado = crear_credito_db(cliente_normal, monto_normal_new, cuotas_normal_new, frecuencia_normal_new, "Normal", fecha_inicio_normal)
                if ok_c:
                    if not err_c:
                        set_flash("credito_msg", "success", f"✅ Crédito {prestamo_creado['id']} creado y contrato enviado correctamente")
                    else:
                        set_flash("credito_msg", "warning", f"⚠️ Crédito {prestamo_creado['id']} creado, pero el contrato quedó pendiente: {err_c}")
                    st.rerun()
                else:
                    st.error(f"❌ {err_c}")
        with tcred2:
            cliente_express = st.selectbox(
                "Cliente",
                clientes_credito_df["cedula"].tolist(),
                key="cliente_express_credito",
                format_func=lambda x: f"{x} — {clientes_credito_df.loc[clientes_credito_df['cedula']==x, 'nombres'].iloc[0]} {clientes_credito_df.loc[clientes_credito_df['cedula']==x, 'apellidos'].iloc[0]}"
            )
            monto_express_new = st.number_input("Monto a prestar", min_value=0.0, step=50000.0, value=300000.0, key="nuevo_monto_express")
            frecuencia_express_new = st.selectbox("Frecuencia", ["Mensual", "Quincenal"], key="nuevo_frec_express")
            cuotas_express_new = 5 if frecuencia_express_new == "Mensual" else 6
            fecha_inicio_express = st.date_input("Fecha de inicio", value=date.today(), key="fecha_inicio_express")
            cuota_preview_express = calcular_cuota_express(monto_express_new, cuotas_express_new, frecuencia_express_new)
            st.info(f"Cuota estimada: {pesos(cuota_preview_express)} | Tasa express: {calcular_tasa_express(frecuencia_express_new)*100:.2f}% | Cuotas: {cuotas_express_new}")
            if st.button("Registrar crédito express", type="primary", key="btn_crear_express"):
                ok_c, err_c, prestamo_creado = crear_credito_db(cliente_express, monto_express_new, cuotas_express_new, frecuencia_express_new, "Express", fecha_inicio_express)
                if ok_c:
                    if not err_c:
                        set_flash("credito_msg", "success", f"✅ Crédito {prestamo_creado['id']} creado y contrato enviado correctamente")
                    else:
                        set_flash("credito_msg", "warning", f"⚠️ Crédito {prestamo_creado['id']} creado, pero el contrato quedó pendiente: {err_c}")
                    st.rerun()
                else:
                    st.error(f"❌ {err_c}")
# ==========================
# 📄 DETALLE
# ==========================
with tab_detalle:
    st.subheader("📄 Detalle por crédito")
    st.caption("Consulta aquí la ficha general del crédito, sus indicadores principales y el detalle de cuotas.")
    show_flash("detalle_msg")
    st.markdown("""
    <style>
    .credit-card {
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 16px 18px;
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        box-shadow: 0 4px 14px rgba(15, 23, 42, .05);
        margin-bottom: 12px;
    }
    .credit-title {
        font-size: 18px;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 6px;
    }
    .credit-sub {
        font-size: 13px;
        color: #64748b;
        margin-bottom: 14px;
    }
    .credit-pill {
        display:inline-block;
        padding:4px 10px;
        border-radius:999px;
        background:#eef2ff;
        color:#3730a3;
        font-size:12px;
        font-weight:700;
        margin-right:8px;
        margin-bottom:8px;
    }
    </style>
    """, unsafe_allow_html=True)
    for _, row in estado.iterrows():
        estado_contrato = "Aceptado" if int(row.get("contrato_aceptado", 0) or 0) == 1 else "Pendiente"
        with st.expander(f"💳 {row['id']} — {row['cliente']}"):
            st.markdown(f"""
            <div class="credit-card">
                <div class="credit-title">Crédito {row['id']}</div>
                <div class="credit-sub">{row['cliente']} • {row['tipo']} • {row['estado']}</div>
                <span class="credit-pill">Frecuencia: {row.get('frecuencia', 'Mensual')}</span>
                <span class="credit-pill">Contrato: {estado_contrato}</span>
                <span class="credit-pill">Tasa mensual: {float(row['tasa_mensual'] or 0):.4f}</span>
            </div>
            """, unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💰 Total del crédito", pesos(row["monto_total_credito"]))
            c2.metric("✅ Total pagado", pesos(row["total_pagado"]))
            c3.metric("🏦 Saldo capital", pesos(row["saldo_capital"]))
            c4.metric("⏳ Saldo pendiente", pesos(row["saldo"]))
            c5, c6, c7 = st.columns(3)
            c5.metric("📌 Cuota actual", pesos(row["valor_cuota"]))
            c6.metric("📆 N.° cuotas", int(row["cuotas"]))
            c7.metric("📝 Estado contrato", estado_contrato)

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
                    st.info("Sin pagos ni abonos registrados para este crédito.")
                else:
                    pagos_credito["valor"] = pagos_credito["valor"].apply(pesos)
                    pagos_credito = pagos_credito.rename(columns={
                        "fecha_pago": "Fecha movimiento",
                        "valor": "Valor",
                        "tipo_movimiento": "Tipo",
                        "detalle": "Detalle"
                    })
                    st.dataframe(pagos_credito, use_container_width=True, hide_index=True)
# ==========================
# 💰 PAGOS
# ==========================
if "pago_msg" not in st.session_state:
    st.session_state.pago_msg = None
with tab_pagos:
    st.subheader("💰 Pagos del crédito")
    st.caption("Separa el pago normal de la cuota y el abono a capital para evitar errores y mantener una operación más clara.")
    activos = estado[estado["estado"] != "Cancelado"]
    if activos.empty:
        st.info("ℹ️ No hay préstamos activos.")
    else:
        opciones = {f"{r.id} — {r.cliente}": r for r in activos.itertuples()}
        seleccion = st.selectbox("📌 Préstamo", list(opciones.keys()))
        prestamo = opciones[seleccion]
        with get_conn() as conn:
            proxima_cuota = obtener_proxima_cuota(conn, prestamo.id)
        fecha_pago = st.date_input("📅 Fecha de movimiento", value=date.today())
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
                with st.form("form_pago_cuota"):
                    st.info("El pago normal registra únicamente la siguiente cuota pendiente del crédito.")
                    confirmar_pago = st.form_submit_button("Registrar pago de cuota", type="primary")
                if confirmar_pago:
                    with st.spinner("⏳ Aplicando pago, por favor espera..."):
                        resultado = registrar_pago_cuota(prestamo.id, fecha_pago)
                        if resultado.get("ok"):
                            st.session_state.pago_msg = {"tipo": "CUOTA", **resultado}
                            time.sleep(0.2)
                            st.rerun()
                        else:
                            st.error(f"❌ {resultado.get('error')}")

        with tab_abono_capital:
            st.caption("El abono a capital reduce el saldo del préstamo y recalcula el valor de las cuotas pendientes, manteniendo el número de cuotas restantes.")
            with st.form("form_abono_capital"):
                abono_capital = st.number_input(
                    "Valor abono a capital",
                    min_value=0.0,
                    step=1000.0,
                    value=0.0,
                    key="abono_capital"
                )
                confirmar_abono = st.form_submit_button("Aplicar abono a capital")
            if confirmar_abono:
                with st.spinner("⏳ Aplicando abono a capital..."):
                    resultado = registrar_abono_capital(prestamo.id, fecha_pago, abono_capital)
                    if resultado.get("ok"):
                        st.session_state.pago_msg = {"tipo": "ABONO_CAPITAL", **resultado}
                        time.sleep(0.2)
                        st.rerun()
                    else:
                        st.error(f"❌ {resultado.get('error')}")
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
