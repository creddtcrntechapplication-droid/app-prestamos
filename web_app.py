
import streamlit as st
import pandas as pd
import os
import smtplib

from datetime import datetime, date
from sqlalchemy import create_engine, text
from email.message import EmailMessage

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
# CONEXIÓN A SUPABASE
# ==========================

DATABASE_URL = st.secrets["DATABASE_URL"]

try:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"sslmode": "require"},
        pool_pre_ping=True
    )
except Exception as e:
    st.error(f"❌ Error al conectar con la base de datos: {e}")
    st.stop()

# ==========================
# FUNCIONES DE UTILIDAD
# ==========================

def get_conn():
    return engine.connect()

def ejecutar_sql(query, params=None, fetch=False):
    params = params or {}
    with get_conn() as conn:
        result = conn.execute(text(query), params)
        if fetch:
            return result.fetchall()
        return result

def pesos(v):
    try:
        return f"${float(v):,.0f}"
    except:
        return "$0"

def calcular_cuotas_pagadas(total_pagado, valor_cuota):
    if valor_cuota == 0:
        return 0
    return int(total_pagado // valor_cuota)

# ==========================
# PRUEBA DE CONEXIÓN
# ==========================

try:
    with get_conn() as conn:
        prueba = conn.execute(text("SELECT 1")).fetchone()
        st.success(f"✅ Conexión exitosa a Supabase! Resultado prueba: {prueba[0]}")
except Exception as e:
    st.error(f"❌ No se pudo conectar a la base de datos: {e}")
    st.stop()

# ==========================
# ESTADO GENERAL
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
            (p.valor_cuota * p.cuotas) - COALESCE(SUM(pg.valor),0) AS saldo,
            c.nombres || ' ' || c.apellidos AS cliente
        FROM prestamos p
        LEFT JOIN pagos pg ON pg.prestamo_id = p.id
        LEFT JOIN clientes c ON c.cedula = p.cliente_cedula
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
# ALERTAS MORA
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
# SIMULADOR
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
# RESUMEN
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
# DETALLE
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
# PAGOS
# ==========================

import time
from decimal import Decimal

if "pago_msg" not in st.session_state:
    st.session_state.pago_msg = None

if "procesando_pago" not in st.session_state:
    st.session_state.procesando_pago = False

if "confirmar_pago" not in st.session_state:
    st.session_state.confirmar_pago = False

if "pago_ejecutado" not in st.session_state:
    st.session_state.pago_ejecutado = False

with tab_pagos:

    st.subheader("💰 Registrar pago")

    activos = estado[estado["estado"] != "Cancelado"]

    if activos.empty:
        st.info("ℹ️ No hay préstamos activos.")
        st.stop()

    opciones = {f"{r.id} — {r.cliente}": r for r in activos.itertuples()}

    seleccion = st.selectbox("📌 Préstamo", list(opciones.keys()))
    prestamo = opciones[seleccion]

    fecha_pago = st.date_input("📅 Fecha de pago", value=date.today())

    valor_pago = st.number_input(
        "💵 Valor pagado",
        min_value=0.0,
        step=1000.0,
        value=float(prestamo.valor_cuota)
    )

    valor_pago = Decimal(str(valor_pago))

    if not st.session_state.confirmar_pago and not st.session_state.procesando_pago:

        if st.button("Registrar pago", type="primary"):

            if valor_pago <= 0:
                st.error("❌ El valor debe ser mayor a cero")
                st.stop()

            st.session_state.confirmar_pago = True
            st.rerun()

    if st.session_state.confirmar_pago and not st.session_state.procesando_pago:

        st.warning(
            f"⚠️ ¿Aplicar pago de {pesos(valor_pago)} al crédito {prestamo.id}?"
        )

        c1, c2 = st.columns(2)

        with c1:
            if st.button("✅ Sí, aplicar"):
                st.session_state.procesando_pago = True
                st.session_state.confirmar_pago = False
                st.rerun()

        with c2:
            if st.button("❌ Cancelar"):
                st.session_state.confirmar_pago = False
                st.rerun()

    if st.session_state.procesando_pago and not st.session_state.pago_ejecutado:

        st.session_state.procesando_pago = False
        st.session_state.pago_ejecutado = True

        with st.spinner("⏳ Aplicando pago, por favor espera..."):

            try:

                with get_conn() as conn:

                    prestamo_db = conn.execute(
                        text("SELECT cliente_cedula, monto_original FROM prestamos WHERE id = :id"),
                        {"id": prestamo.id}
                    ).fetchone()

                    if not prestamo_db:
                        st.error("❌ No se pudo obtener el préstamo")
                        st.stop()

                    cliente_cedula, monto_original = prestamo_db

                    cuotas = conn.execute(
                        text("""
                        SELECT id_cuota, valor_cuota, nro_cuota
                        FROM cuotas
                        WHERE prestamo_id = :id
                        AND estado <> 'Pagada'
                        ORDER BY nro_cuota ASC
                        """),
                        {"id": prestamo.id}
                    ).fetchall()

                    if not cuotas:
                        st.info("ℹ️ Todas las cuotas ya están pagadas.")
                        st.stop()

                    pagos_cuotas = conn.execute(
                        text("""
                            SELECT pc.id_cuota, COALESCE(SUM(p.valor),0)
                            FROM pagos p
                            JOIN pagos_cuotas pc ON p.id_pago = pc.id_pago
                            WHERE p.prestamo_id = :id
                            GROUP BY pc.id_cuota
                        """),
                        {"id": prestamo.id}
                    ).fetchall()

                    pagos_dict = {r[0]: r[1] for r in pagos_cuotas}

                    pago_restante = valor_pago
                    primera_cuota_afectada = None
                    cuotas_afectadas = []

                    for id_cuota, valor_cuota, nro in cuotas:

                        if pago_restante <= 0:
                            break

                        pagado_actual = pagos_dict.get(id_cuota, 0)
                        saldo_cuota = valor_cuota - pagado_actual
                        abono = min(saldo_cuota, pago_restante)

                        if abono <= 0:
                            continue

                        if primera_cuota_afectada is None:
                            primera_cuota_afectada = nro

                        cuotas_afectadas.append((id_cuota, saldo_cuota, abono))
                        pago_restante -= abono

                    if not cuotas_afectadas:
                        st.warning("⚠️ No se pudo aplicar el pago a ninguna cuota.")
                        st.stop()

                    result_pago = conn.execute(
                        text("""
                            INSERT INTO pagos (prestamo_id, fecha_pago, valor, estado)
                            VALUES (:id, :fecha, :valor, 'Pagado')
                            RETURNING id_pago
                        """),
                        {
                            "id": prestamo.id,
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

                        nuevo_estado = "Pagada" if abono == saldo_cuota else "Parcial"

                        conn.execute(
                            text("""
                                UPDATE cuotas
                                SET estado = :estado
                                WHERE id_cuota = :id_cuota
                            """),
                            {"estado": nuevo_estado, "id_cuota": id_cuota}
                        )

                    restantes = conn.execute(
                        text("""
                        SELECT COUNT(*)
                        FROM cuotas
                        WHERE prestamo_id = :id
                        AND estado <> 'Pagada'
                        """),
                        {"id": prestamo.id}
                    ).fetchone()[0]

                    if restantes == 0:
                        conn.execute(
                            text("UPDATE prestamos SET estado = 'Cerrado' WHERE id = :id"),
                            {"id": prestamo.id}
                        )

                    conn.commit()

                st.session_state.pago_msg = {
                    "credito": prestamo.id,
                    "cuota": primera_cuota_afectada
                }

                time.sleep(0.3)
                st.rerun()

            except Exception as e:

                st.error(f"❌ Error al registrar pago: {e}")

    if st.session_state.pago_msg:

        m = st.session_state.pago_msg

        st.success(
            f"Pago registrado\n"
            f"Crédito: {m['credito']}\n"
            f"Cuota: #{m['cuota']}"
        )

        st.session_state.pago_msg = None

# ==========================
# ALERTAS
# ==========================

st.subheader("⚠ Alertas de cartera")

col1, col2 = st.columns(2)

with col1:
    st.metric("Clientes en mora", clientes_mora)

with col2:
    st.metric("Monto en mora", f"${monto_mora:,.0f}")

# ==========================
# SIMULADOR
# ==========================

with tab_sim:

    st.subheader("🧮 Simulador de crédito")

    t1, t2 = st.tabs([
        "💳 Crédito normal",
        "⚡ Crédito express"
    ])

    with t1:

        monto_normal = st.number_input(
            "Monto del crédito",
            min_value=100_000,
            step=100_000,
            value=1_000_000
        )

        cuotas_normal = st.selectbox(
            "Número de cuotas",
            [12, 15]
        )

        if st.button("Calcular crédito normal"):

            cuota = calcular_cuota_normal(monto_normal, cuotas_normal)

            st.success(
                f"📌 Cuota mensual: **{pesos(cuota)}**\n\n"
                f"📆 Total cuotas: **{cuotas_normal}**\n\n"
                f"💰 Total a pagar: **{pesos(cuota * cuotas_normal)}**"
            )

    with t2:

        monto_express = st.number_input(
            "Monto del crédito express",
            min_value=50_000,
            step=50_000,
            value=200_000
        )

        frecuencia = st.selectbox(
            "Frecuencia de pago",
            ["Mensual", "Quincenal"]
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
