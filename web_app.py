import streamlit as st
import pandas as pd
import os
import tempfile
import base64
import requests

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

# ==========================
# UTILIDADES
# ==========================
def pesos(valor):
    return f"${int(valor):,}".replace(",", ".")

def enviar_correo(destino, asunto, cuerpo):
    ok, error = enviar_correo_mailersend(
        destino=destino,
        asunto=asunto,
        cuerpo=cuerpo
    )
    if not ok:
        st.warning(f"⚠️ El correo no pudo enviarse: {error}")

def calcular_cuotas_pagadas(total_pagado, valor_cuota):
    if valor_cuota <= 0:
        return 0
    return int(total_pagado // valor_cuota)


def generar_recibo_pdf(prestamo_id, cliente, monto_credito, fecha_pago, valor_pagado):

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

    elementos.append(Paragraph("RECIBO DE PAGO", estilo_titulo))

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

    elementos.append(Paragraph("VALOR PAGADO", estilo_pago_label))
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
        """
        SELECT
            p.id,
            p.estado,
            p.monto_original,

            (p.valor_cuota * p.cuotas) AS monto_total_credito,

            p.valor_cuota,
            p.cuotas,
            p.tipo,

            COALESCE(SUM(pg.valor),0) AS total_pagado,

            (p.valor_cuota * p.cuotas)
            - COALESCE(SUM(pg.valor),0) AS saldo,

            c.nombres || ' ' || c.apellidos AS cliente

        FROM prestamos p

        LEFT JOIN pagos pg
            ON pg.prestamo_id = p.id

        LEFT JOIN clientes c
            ON c.cedula = p.cliente_cedula

        GROUP BY
            p.id,
            p.estado,
            p.monto_original,
            p.valor_cuota,
            p.cuotas,
            p.tipo,
            c.nombres,
            c.apellidos

        ORDER BY p.id DESC
        """,
        conn
    )


# asegurar tipos numéricos
for col in [
    "monto_original",
    "monto_total_credito",
    "valor_cuota",
    "total_pagado",
    "saldo"
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
    st.subheader("📊 Resumen general")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Total colocado", pesos(estado["monto_original"].sum()))
    k2.metric("✅ Total cobrado", pesos(estado["total_pagado"].sum()))
    k3.metric("⏳ Saldo pendiente", pesos(estado["saldo"].sum()))
    k4.metric("📄 Créditos activos", estado[estado["estado"] != "Cancelado"].shape[0])

    st.divider()

    df = estado.copy()
    for c in ["monto_original","monto_total_credito","total_pagado","saldo","valor_cuota"]:
        df[c] = df[c].apply(pesos)

    st.dataframe(df[
        ["id","cliente","monto_original","monto_total_credito",
         "total_pagado","saldo","valor_cuota","cuotas","tipo","estado"]
    ], use_container_width=True)

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

    # 🔥 ÚNICO CAMBIO REAL: <=

    # Corregido: Indentación alineada y uso de parámetros PostgreSQL
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
    pagado_periodo = cuotas_df[cuotas_df["estado"]=="Pagada"]["valor_cuota"].sum()
    pendiente_periodo = cuotas_df[cuotas_df["estado"].isin(["Pendiente","Parcial"])]["valor_cuota"].sum()

    c1,c2,c3 = st.columns(3)

    with c1:
        if st.button("📥 Cuotas del período"):
            st.session_state.detalle="total"
        st.metric("", pesos(total_periodo))

    with c2:
        if st.button("✅ Pagado en el período"):
            st.session_state.detalle="pagado"
        st.metric("", pesos(pagado_periodo))

    with c3:
        if st.button("⏳ Pendiente del período"):
            st.session_state.detalle="pendiente"
        st.metric("", pesos(pendiente_periodo))

    # ==========================
    # 🟦 CARDS
    # ==========================
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
# 📄 DETALLE
# ==========================
with tab_detalle:
    st.subheader("📄 Detalle por crédito")

    for _, row in estado.iterrows():
        cuotas_pagadas = calcular_cuotas_pagadas(
            row["total_pagado"],
            row["valor_cuota"]
        )

        with st.expander(f"💳 Préstamo {row['id']} — {row['cliente']}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Total crédito", pesos(row["monto_total_credito"]))
            c2.metric("✅ Pagado", pesos(row["total_pagado"]))
            c3.metric("⏳ Saldo", pesos(row["saldo"]))

            st.markdown("### 🧾 Estado de cuotas")
            for i in range(1, row["cuotas"] + 1):
                if i <= cuotas_pagadas:
                    st.success(f"Cuota {i} — PAGADA")
                else:
                    st.warning(f"Cuota {i} — PENDIENTE")

# ==========================
# 💰 PAGOS
# ==========================

import time
from decimal import Decimal

if "pago_msg" not in st.session_state:
    st.session_state.pago_msg = None

if "procesando_pago" not in st.session_state:
    st.session_state.procesando_pago = False

if "confirmar_pago" not in st.session_state:
    st.session_state.confirmar_pago = False

if "app_bloqueada" not in st.session_state:
    st.session_state.app_bloqueada = False

if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

if "confirmar_pago_data" not in st.session_state:
    st.session_state.confirmar_pago_data = None


def procesar_accion_pendiente():
    accion = st.session_state.get("pending_action")
    if not accion:
        return

    st.session_state.app_bloqueada = True
    tipo_accion = accion.get("tipo")

    try:
        with st.spinner("⏳ Procesando, por favor espera..."):
            if tipo_accion == "PAGO_CUOTA":
                prestamo_id = accion["prestamo_id"]
                fecha_pago = accion["fecha_pago"]
                valor_pago = Decimal(str(accion["valor_pago"]))
                with get_conn() as conn:

                    prestamo_db = conn.execute(
                        text("SELECT cliente_cedula, monto_original FROM prestamos WHERE id = :id"),
                        {"id": prestamo_id}
                    ).fetchone()

                    if not prestamo_db:
                        raise Exception("No se pudo obtener el préstamo")

                    cliente_cedula, monto_original = prestamo_db

                    cuotas = conn.execute(
                        text("""
                            SELECT id_cuota, valor_cuota, nro_cuota
                            FROM cuotas
                            WHERE prestamo_id = :id
                            AND estado <> 'Pagada'
                            ORDER BY nro_cuota ASC
                        """),
                        {"id": prestamo_id}
                    ).fetchall()

                    if not cuotas:
                        raise Exception("Todas las cuotas ya están pagadas.")

                    pagos_cuotas = conn.execute(
                        text("""
                            SELECT pc.id_cuota, COALESCE(SUM(p.valor),0)
                            FROM pagos p
                            JOIN pagos_cuotas pc ON p.id_pago = pc.id_pago
                            WHERE p.prestamo_id = :id
                            GROUP BY pc.id_cuota
                        """),
                        {"id": prestamo_id}
                    ).fetchall()

                    pagos_dict = {r[0]: r[1] for r in pagos_cuotas}

                    pago_restante = valor_pago
                    primera_cuota_afectada = None
                    cuotas_afectadas = []

                    for id_cuota, valor_cuota_db, nro in cuotas:
                        if pago_restante <= 0:
                            break

                        pagado_actual = pagos_dict.get(id_cuota, 0)
                        saldo_cuota = valor_cuota_db - pagado_actual
                        abono = min(saldo_cuota, pago_restante)

                        if abono <= 0:
                            continue

                        if primera_cuota_afectada is None:
                            primera_cuota_afectada = nro

                        cuotas_afectadas.append((id_cuota, saldo_cuota, abono))
                        pago_restante -= abono

                    if not cuotas_afectadas:
                        raise Exception("No se pudo aplicar el pago.")

                    result_pago = conn.execute(
                        text("""
                            INSERT INTO pagos (prestamo_id, fecha_pago, valor, estado)
                            VALUES (:id, :fecha, :valor, 'Pagado')
                            RETURNING id_pago
                        """),
                        {
                            "id": prestamo_id,
                            "fecha": fecha_pago.isoformat(),
                            "valor": valor_pago
                        }
                    )

                    id_pago = result_pago.fetchone()[0]

                    for id_cuota, saldo_cuota, abono in cuotas_afectadas:
                        conn.execute(
                            text("""
                                INSERT INTO pagos_cuotas (id_pago, id_cuota)
                                VALUES (:id_pago, :id_cuota)
                            """),
                            {"id_pago": id_pago, "id_cuota": id_cuota}
                        )

                        estado_cuota = "Pagada" if abono == saldo_cuota else "Parcial"

                        conn.execute(
                            text("""
                                UPDATE cuotas
                                SET estado = :estado
                                WHERE id_cuota = :id_cuota
                            """),
                            {"estado": estado_cuota, "id_cuota": id_cuota}
                        )

                    conn.commit()

                    cliente = conn.execute(
                        text("""
                            SELECT nombres || ' ' || apellidos, correo
                            FROM clientes
                            WHERE cedula = :cedula
                        """),
                        {"cedula": cliente_cedula}
                    ).fetchone()

                nombre_cliente = cliente[0] if cliente else "Cliente"
                correo_cliente = (cliente[1] or "").strip() if cliente else ""

                correo_ok = False

                if correo_cliente:
                    try:
                        pdf = generar_recibo_pdf(
                            prestamo_id,
                            nombre_cliente,
                            monto_original,
                            fecha_pago.isoformat(),
                            valor_pago
                        )

                        with open(pdf, "rb") as f:
                            correo_ok = enviar_correo_async(
                                correo_cliente,
                                f"Recibo pago {prestamo_id}",
                                f"Hola {nombre_cliente}, pago recibido.",
                                attachment_bytes=f.read(),
                                attachment_name=f"recibo_{prestamo_id}.pdf"
                            )
                    except Exception as e:
                        st.error(f"❌ Error enviando correo: {e}")
                        correo_ok = False

                st.session_state.pago_msg = {
                    "credito": prestamo_id,
                    "cuota": primera_cuota_afectada,
                    "correo": correo_ok,
                    "tiene_correo": bool(correo_cliente)
                }
                st.session_state.confirmar_pago = False
                st.session_state.confirmar_pago_data = None
                st.session_state["select_prestamo_pago"] = None

    except Exception as e:
        st.error(f"❌ Error: {e}")
    finally:
        st.session_state.app_bloqueada = False
        st.session_state.pending_action = None
        st.rerun()


if st.session_state.get("pending_action"):
    procesar_accion_pendiente()


with tab_pagos:
    st.subheader("💰 Registrar pago")

    activos = estado[estado["estado"] != "Cancelado"]

    if activos.empty:
        st.info("ℹ️ No hay préstamos activos.")
        st.stop()

    opciones = {f"{r.id} — {r.cliente}": r for r in activos.itertuples()}
    opciones_lista = [None] + list(opciones.keys())

    with st.form("form_pago_credito", clear_on_submit=True):
        seleccion = st.selectbox(
            "📌 Préstamo",
            opciones_lista,
            index=0,
            key="select_prestamo_pago",
            format_func=lambda x: "Selecciona un préstamo" if x is None else x
        )

        prestamo = opciones.get(seleccion) if seleccion else None

        fecha_pago = st.date_input("📅 Fecha de pago", value=date.today())

        valor_default = float(prestamo.valor_cuota) if prestamo is not None else 0.0
        valor_pago = st.number_input(
            "💵 Valor pagado",
            min_value=0.0,
            step=1000.0,
            value=valor_default
        )

        enviar_pago = st.form_submit_button(
            "Registrar pago",
            type="primary",
            disabled=st.session_state.app_bloqueada
        )

    if st.session_state.app_bloqueada:
        st.info("⏳ Hay un proceso en curso. Espera a que termine para continuar.")

    if enviar_pago:
        if seleccion is None:
            st.warning("⚠️ Selecciona un préstamo antes de registrar el pago.")
        elif valor_pago <= 0:
            st.error("❌ El valor debe ser mayor a cero")
        else:
            st.session_state.confirmar_pago_data = {
                "prestamo_id": prestamo.id,
                "cliente": prestamo.cliente,
                "fecha_pago": fecha_pago,
                "valor_pago": str(Decimal(str(valor_pago)))
            }
            st.session_state.confirmar_pago = True
            st.rerun()

    if st.session_state.confirmar_pago and st.session_state.confirmar_pago_data and not st.session_state.app_bloqueada:
        data_pago = st.session_state.confirmar_pago_data
        st.warning(
            f"⚠️ ¿Aplicar pago de {pesos(Decimal(data_pago['valor_pago']))} al crédito {data_pago['prestamo_id']}?"
        )

        c1, c2 = st.columns(2)

        with c1:
            if st.button("✅ Sí, aplicar", disabled=st.session_state.app_bloqueada):
                st.session_state.pending_action = {
                    "tipo": "PAGO_CUOTA",
                    "prestamo_id": data_pago["prestamo_id"],
                    "fecha_pago": data_pago["fecha_pago"],
                    "valor_pago": data_pago["valor_pago"]
                }
                st.session_state.app_bloqueada = True
                st.session_state.confirmar_pago = False
                st.rerun()

        with c2:
            if st.button("❌ Cancelar", disabled=st.session_state.app_bloqueada):
                st.session_state.confirmar_pago = False
                st.session_state.confirmar_pago_data = None
                st.rerun()
    if st.session_state.pago_msg:
        m = st.session_state.pago_msg

        if m["tiene_correo"] and m["correo"]:
            st.success(f"✅ Pago registrado y correo enviado - Crédito {m['credito']}")
        elif m["tiene_correo"] and not m["correo"]:
            st.warning(f"⚠️ Pago registrado, pero el correo no se pudo enviar - Crédito {m['credito']}")
            if m.get("correo_error"):
                st.error(f"Detalle correo: {m['correo_error']}")
        else:
            st.success("✅ Pago registrado (sin correo)")

        st.session_state.pago_msg = None

# ==========================
# ALERTAS DE CARTERA
# ==========================

st.subheader("⚠ Alertas de cartera")

col1, col2 = st.columns(2)

with col1:
    st.metric("Clientes en mora", clientes_mora)

with col2:
    st.metric("Monto en mora", f"${monto_mora:,.0f}")
    

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
