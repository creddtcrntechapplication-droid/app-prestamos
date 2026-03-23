import streamlit as st
import pandas as pd
import os
import tempfile
import base64
import requests
import math
import time
from decimal import Decimal

from datetime import datetime, date
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
# PRUEBA DE CONEXIÓN
# ==========================
try:
    with get_conn() as conn:
        prueba = conn.execute(text("SELECT 1")).fetchone()
        st.success(f"✅ Conexión exitosa a Supabase! Resultado prueba: {prueba[0]}")
except Exception as e:
    st.error(f"❌ No se pudo conectar a la base de datos: {e}")



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
if "auth" not in st.session_state:
    st.session_state.auth = False
    st.session_state.usuario = None
    st.session_state.rol = None

if not st.session_state.auth:
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
        return enviar_pdf_por_correo(
            prestamo_row["correo"],
            f"Contrato crédito {prestamo_row['id']}",
            cuerpo,
            ruta_pdf,
            f"contrato_{prestamo_row['id']}.pdf"
        )
    finally:
        if ruta_pdf and os.path.exists(ruta_pdf):
            try:
                os.remove(ruta_pdf)
            except Exception:
                pass


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
        attachment_name=None
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
            "html": html_template
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
        attachment_name=None
):
    return enviar_correo_mailersend(
        destino=destino,
        asunto=asunto,
        cuerpo=cuerpo,
        attachment_bytes=attachment_bytes,
        attachment_name=attachment_name
    )

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
            p.tipo,
            p.cliente_cedula,
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
            p.id, p.estado, p.monto_original, p.valor_cuota, p.cuotas, p.tipo,
            p.cliente_cedula, p.saldo_capital, p.tasa_mensual, c.nombres, c.apellidos, c.correo
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

def calcular_cuota_normal(monto, cuotas):
    if cuotas == 0:
        return 0
    return monto / cuotas


def calcular_cuota_express(monto, cuotas, frecuencia):
    if cuotas == 0:
        return 0

    interes = 0.20
    total = monto + (monto * interes)

    return total / cuotas



# ==========================
# TABS
# ==========================
tab_resumen, tab_detalle, tab_pagos, tab_sim = st.tabs([
    "📊 Resumen",
    "📄 Detalle por crédito",
    "💰 Pagos",
    "🧮 Simulador"
])

# ==========================
# 📊 RESUMEN
# ==========================
with tab_resumen:
    st.markdown("""
    <style>
    .dashboard-card {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 18px 18px 14px 18px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
        margin-bottom: 12px;
    }
    .dashboard-card-title {
        font-size: 13px;
        color: #64748b;
        margin-bottom: 8px;
        font-weight: 600;
    }
    .dashboard-card-value {
        font-size: 28px;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.1;
    }
    .dashboard-card-sub {
        font-size: 12px;
        color: #94a3b8;
        margin-top: 6px;
    }
    .risk-card {
        border-radius: 18px;
        padding: 18px;
        color: #0f172a;
        border: 1px solid #fde68a;
        background: linear-gradient(180deg, #fffdf7 0%, #fffbeb 100%);
        box-shadow: 0 4px 14px rgba(245, 158, 11, 0.08);
        min-height: 140px;
        margin-bottom: 12px;
    }
    .risk-title {
        font-size: 13px;
        color: #92400e;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .risk-value {
        font-size: 30px;
        font-weight: 800;
        color: #7c2d12;
        line-height: 1.1;
    }
    .risk-sub {
        font-size: 12px;
        color: #a16207;
        margin-top: 8px;
    }
    .section-box {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
        margin-bottom: 16px;
    }
    .section-title {
        font-size: 18px;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .section-subtitle {
        font-size: 13px;
        color: #64748b;
        margin-bottom: 14px;
    }
    .mini-card {
        background: #ffffff;
        color: #111827;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,.05);
        margin-bottom: 12px;
    }
    .mini-card-title {
        font-size: 13px;
        color: #64748b;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .mini-card-value {
        font-size: 26px;
        font-weight: 800;
        color: #0f172a;
    }
    .mini-card-foot {
        font-size: 12px;
        color: #94a3b8;
        margin-top: 6px;
    }
    </style>
    """, unsafe_allow_html=True)

    total_colocado = estado["monto_original"].sum()
    total_cobrado = estado["total_pagado"].sum()
    saldo_pendiente = estado["saldo"].sum()
    creditos_activos = estado[estado["estado"] != "Cancelado"].shape[0]
    mora_ratio = 0 if saldo_pendiente <= 0 else (monto_mora / saldo_pendiente) * 100

    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📊 Resumen general</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Vista ejecutiva del comportamiento actual de la cartera, el recaudo y el nivel de riesgo.</div>', unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.markdown(f'''
        <div class="dashboard-card">
            <div class="dashboard-card-title">💰 Total colocado</div>
            <div class="dashboard-card-value">{pesos(total_colocado)}</div>
            <div class="dashboard-card-sub">Capital total desembolsado</div>
        </div>
        ''', unsafe_allow_html=True)

    with k2:
        st.markdown(f'''
        <div class="dashboard-card">
            <div class="dashboard-card-title">✅ Total cobrado</div>
            <div class="dashboard-card-value">{pesos(total_cobrado)}</div>
            <div class="dashboard-card-sub">Recaudo acumulado registrado</div>
        </div>
        ''', unsafe_allow_html=True)

    with k3:
        st.markdown(f'''
        <div class="dashboard-card">
            <div class="dashboard-card-title">⏳ Saldo pendiente</div>
            <div class="dashboard-card-value">{pesos(saldo_pendiente)}</div>
            <div class="dashboard-card-sub">Saldo total aún por recuperar</div>
        </div>
        ''', unsafe_allow_html=True)

    with k4:
        st.markdown(f'''
        <div class="dashboard-card">
            <div class="dashboard-card-title">📄 Créditos activos</div>
            <div class="dashboard-card-value">{creditos_activos}</div>
            <div class="dashboard-card-sub">Créditos vigentes no cancelados</div>
        </div>
        ''', unsafe_allow_html=True)

    r1, r2, r3 = st.columns(3)

    with r1:
        st.markdown(f'''
        <div class="risk-card">
            <div class="risk-title">⚠ Clientes en mora</div>
            <div class="risk-value">{clientes_mora}</div>
            <div class="risk-sub">Créditos con alerta prioritaria de seguimiento</div>
        </div>
        ''', unsafe_allow_html=True)

    with r2:
        st.markdown(f'''
        <div class="risk-card">
            <div class="risk-title">💸 Monto en mora</div>
            <div class="risk-value">{pesos(monto_mora)}</div>
            <div class="risk-sub">Valor acumulado vencido en cartera</div>
        </div>
        ''', unsafe_allow_html=True)

    with r3:
        st.markdown(f'''
        <div class="risk-card">
            <div class="risk-title">📌 Exposición en mora</div>
            <div class="risk-value">{mora_ratio:.1f}%</div>
            <div class="risk-sub">Participación del atraso sobre el saldo pendiente</div>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📋 Detalle general de créditos</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Resumen consolidado por crédito con estado, cuota, saldo y tipo.</div>', unsafe_allow_html=True)

    df = estado.copy()
    for c in ["monto_original", "monto_total_credito", "total_pagado", "saldo", "valor_cuota"]:
        df[c] = df[c].apply(pesos)

    st.dataframe(
        df[[
            "id", "cliente", "monto_original", "monto_total_credito",
            "total_pagado", "saldo", "valor_cuota", "cuotas", "tipo", "estado"
        ]],
        use_container_width=True,
        hide_index=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🔎 Consulta mensual</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Corte operativo del período para análisis de cuotas, recaudo y pendientes.</div>', unsafe_allow_html=True)

    mes_consulta = st.selectbox(
        "Selecciona el mes",
        pd.date_range("2025-12-01", "2030-12-01", freq="MS").strftime("%Y-%m")
    )

    year, month = map(int, mes_consulta.split("-"))

    if year == 2025 and month == 12:
        inicio = datetime(2025, 12, 15)
        fin = datetime(2026, 1, 1)
    elif year == 2026 and month == 1:
        inicio = datetime(2026, 1, 1)
        fin = datetime(2026, 2, 2)
    else:
        inicio = datetime(year, month, 3)
        fin = datetime(year + (month == 12), 1 if month == 12 else month + 1, 2)

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
    pagado_periodo = cuotas_df[cuotas_df["estado"] == "Pagada"]["valor_cuota"].sum() if not cuotas_df.empty else 0
    pendiente_periodo = cuotas_df[cuotas_df["estado"].isin(["Pendiente", "Parcial"])]["valor_cuota"].sum() if not cuotas_df.empty else 0

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(f'''
        <div class="mini-card">
            <div class="mini-card-title">📥 Cuotas del período</div>
            <div class="mini-card-value">{pesos(total_periodo)}</div>
            <div class="mini-card-foot">Total programado en el corte seleccionado</div>
        </div>
        ''', unsafe_allow_html=True)
        if st.button("Ver cuotas del período", key="btn_total_periodo"):
            st.session_state.detalle = "total"

    with c2:
        st.markdown(f'''
        <div class="mini-card">
            <div class="mini-card-title">✅ Pagado en el período</div>
            <div class="mini-card-value">{pesos(pagado_periodo)}</div>
            <div class="mini-card-foot">Cuotas cubiertas dentro del corte</div>
        </div>
        ''', unsafe_allow_html=True)
        if st.button("Ver pagadas", key="btn_pagado_periodo"):
            st.session_state.detalle = "pagado"

    with c3:
        st.markdown(f'''
        <div class="mini-card">
            <div class="mini-card-title">⏳ Pendiente del período</div>
            <div class="mini-card-value">{pesos(pendiente_periodo)}</div>
            <div class="mini-card-foot">Cuotas aún pendientes o parciales</div>
        </div>
        ''', unsafe_allow_html=True)
        if st.button("Ver pendientes", key="btn_pendiente_periodo"):
            st.session_state.detalle = "pendiente"

    if "detalle" in st.session_state and not cuotas_df.empty:
        st.markdown("---")

        if st.session_state.detalle == "total":
            df_detalle = cuotas_df
            titulo = "📋 Todas las cuotas del período"
        elif st.session_state.detalle == "pagado":
            df_detalle = cuotas_df[cuotas_df["estado"] == "Pagada"]
            titulo = "✅ Cuotas pagadas del período"
        else:
            df_detalle = cuotas_df[cuotas_df["estado"].isin(["Pendiente", "Parcial"])]
            titulo = "⏳ Cuotas pendientes del período"

        st.markdown(f'<div class="section-title">{titulo}</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Detalle visual de las cuotas asociadas al corte seleccionado.</div>', unsafe_allow_html=True)

        cols = st.columns(3)
        for i, r in enumerate(df_detalle.itertuples()):
            with cols[i % 3]:
                if r.estado == "Pagada":
                    estado_color = "🟢 Pagada"
                elif r.estado == "Parcial":
                    estado_color = "🟡 Parcial"
                else:
                    estado_color = "🔴 Pendiente"

                st.markdown(f"""
                <div class=\"mini-card\">
                    <div class=\"mini-card-title\">{r.cliente}</div>
                    <div style=\"font-size:13px;color:#64748b;\">Cuota #{r.nro_cuota} · {r.fecha_vencimiento}</div>
                    <div class=\"mini-card-value\" style=\"font-size:22px;margin-top:8px;\">{pesos(r.valor_cuota)}</div>
                    <div class=\"mini-card-foot\">{estado_color}</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
# ==========================
# 📄 DETALLE
# ==========================
with tab_detalle:
    st.subheader("📄 Detalle por crédito")

    for _, row in estado.iterrows():
        with st.expander(f"💳 Préstamo {row['id']} — {row['cliente']}"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💰 Total crédito actual", pesos(row["monto_total_credito"]))
            c2.metric("✅ Pagado", pesos(row["total_pagado"]))
            c3.metric("🏦 Saldo capital", pesos(row["saldo_capital"]))
            c4.metric("⏳ Saldo cuotas", pesos(row["saldo"]))

            st.caption(f"Tasa mensual actual: {float(row['tasa_mensual'] or 0):.4f} | Cuota actual: {pesos(row['valor_cuota'])}")

            with get_conn() as conn:
                cuotas_credito = pd.read_sql(text("""
                    SELECT nro_cuota, fecha_vencimiento, valor_cuota, estado
                    FROM cuotas
                    WHERE prestamo_id = :id
                    ORDER BY nro_cuota ASC
                """), conn, params={"id": row["id"]})

            if cuotas_credito.empty:
                st.info("Sin cuotas registradas para este crédito.")
            else:
                cuotas_credito["valor_cuota"] = cuotas_credito["valor_cuota"].apply(pesos)
                st.dataframe(cuotas_credito, use_container_width=True, hide_index=True)

            b1, b2 = st.columns(2)
            if b1.button("📄 Enviar contrato", key=f"contrato_{row['id']}"):
                ok, error = enviar_contrato_credito(row.to_dict())
                if ok:
                    st.success("✅ Contrato enviado correctamente")
                else:
                    st.error(f"❌ No se pudo enviar el contrato: {error}")

            if b2.button("⏰ Enviar recordatorio", key=f"recordatorio_{row['id']}"):
                ok, error = enviar_recordatorio_credito(row.to_dict())
                if ok:
                    st.success("✅ Recordatorio enviado correctamente")
                else:
                    st.error(f"❌ No se pudo enviar el recordatorio: {error}")

# ==========================
# 💰 PAGOS
# ==========================

if "pago_msg" not in st.session_state:
    st.session_state.pago_msg = None

with tab_pagos:
    st.subheader("💰 Pagos del crédito")

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
        st.markdown("### ✅ Pago de cuota")

        if not proxima_cuota:
            st.info("ℹ️ Este crédito no tiene cuotas pendientes.")
        else:
            st.info(
                f"Próxima cuota a pagar: #{proxima_cuota[1]} | Vence: {proxima_cuota[3]} | Valor exacto: {pesos(proxima_cuota[2])}"
            )

            if st.button("Registrar pago de cuota", type="primary", key="btn_pago_cuota"):
                with st.spinner("⏳ Aplicando pago, por favor espera..."):
                    resultado = registrar_pago_cuota(prestamo.id, fecha_pago)
                    if resultado.get("ok"):
                        st.session_state.pago_msg = {"tipo": "CUOTA", **resultado}
                        time.sleep(0.2)
                        st.rerun()
                    else:
                        st.error(f"❌ {resultado.get('error')}")

        st.divider()
        st.markdown("### 🏦 Abono a capital")
        st.caption("El abono a capital reduce el saldo del préstamo y recalcula el valor de las cuotas pendientes, manteniendo el número de cuotas restantes.")

        abono_capital = st.number_input(
            "Valor abono a capital",
            min_value=0.0,
            step=1000.0,
            value=0.0,
            key="abono_capital"
        )

        if st.button("Aplicar abono a capital", key="btn_abono_capital"):
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
                f"💰 Total a pagar: **{pesos(cuota * cuotas_express)}**"
            )
