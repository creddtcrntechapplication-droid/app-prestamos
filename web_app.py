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
from zoneinfo import ZoneInfo
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
APP_TIMEZONE = get_config("APP_TIMEZONE", "America/Bogota")

def ahora_local():
    return datetime.now(ZoneInfo(APP_TIMEZONE))

def hoy_local():
    return ahora_local().date()
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

def clear_app_caches():
    try:
        load_estado.cache_clear()
        load_mora.cache_clear()
        load_cuotas_periodo.cache_clear()
        load_cuotas_proyeccion.cache_clear()
        load_detalle_mora.cache_clear()
        load_kpis_financieros.cache_clear()
    except Exception:
        pass

@st.cache_data(ttl=45, show_spinner=False)
def load_estado():
    with get_conn() as conn:
        df = pd.read_sql(
            text("""
            SELECT
                p.id,
                p.estado,
                p.monto_original,
                p.valor_cuota,
                p.cuotas,
                COALESCE(p.frecuencia, 'Mensual') AS frecuencia,
                p.tipo,
                CASE
                    WHEN (
                    LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                ) THEN 'interes_libre'
                    WHEN LOWER(TRIM(COALESCE(p.tipo, ''))) = 'express' THEN 'express'
                    ELSE COALESCE(NULLIF(p.tipo_credito, ''), 'normal')
                END AS tipo_credito_codigo,
                p.cliente_cedula,
                COALESCE(p.contrato_aceptado, 0) AS contrato_aceptado,
                COALESCE(p.contrato_enviado, 0) AS contrato_enviado,
                COALESCE(p.desembolso_notificado, 0) AS desembolso_notificado,
                COALESCE(p.contrato_cancelado, 0) AS contrato_cancelado,
                p.fecha_envio_contrato,
                p.fecha_aceptacion,
                p.fecha_desembolso,
                p.fecha_cancelacion_contrato,
                p.motivo_cancelacion_contrato,
                p.cancelado_por,
                COALESCE(p.saldo_capital, p.monto_original) AS saldo_capital,
                COALESCE(p.tasa_mensual, 0) AS tasa_mensual,
                COALESCE(p.interes_acumulado, 0) AS interes_acumulado,
                p.fecha_ultimo_corte_interes,
                p.fecha_proximo_interes,
                p.fecha_cierre_manual,
                COALESCE(SUM(pg.valor),0) AS total_pagado,
                CASE
                    WHEN (
                    LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                )
                    THEN COALESCE(p.saldo_capital, p.monto_original) + COALESCE(p.interes_acumulado, 0)
                    ELSE COALESCE((
                        SELECT SUM(cu.valor_cuota)
                        FROM cuotas cu
                        WHERE cu.prestamo_id = p.id
                          AND cu.estado <> 'Pagada'
                    ),0)
                END AS saldo,
                COALESCE(SUM(pg.valor),0) + CASE
                    WHEN (
                    LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                )
                    THEN COALESCE(p.saldo_capital, p.monto_original) + COALESCE(p.interes_acumulado, 0)
                    ELSE COALESCE((
                        SELECT SUM(cu.valor_cuota)
                        FROM cuotas cu
                        WHERE cu.prestamo_id = p.id
                          AND cu.estado <> 'Pagada'
                    ),0)
                END AS monto_total_credito,
                c.nombres || ' ' || c.apellidos AS cliente,
                c.correo
            FROM prestamos p
            LEFT JOIN pagos pg
                ON pg.prestamo_id = p.id
            LEFT JOIN clientes c
                ON c.cedula = p.cliente_cedula
            GROUP BY
                p.id, p.estado, p.monto_original, p.valor_cuota, p.cuotas, p.frecuencia, p.tipo, p.tipo_credito,
                p.cliente_cedula, p.contrato_aceptado, p.contrato_enviado, p.desembolso_notificado, p.contrato_cancelado,
                p.fecha_envio_contrato, p.fecha_aceptacion, p.fecha_desembolso, p.fecha_cancelacion_contrato,
                p.motivo_cancelacion_contrato, p.cancelado_por,
                p.saldo_capital, p.tasa_mensual, p.interes_acumulado, p.fecha_ultimo_corte_interes, p.fecha_proximo_interes, p.fecha_cierre_manual, c.nombres, c.apellidos, c.correo
            ORDER BY p.id DESC
            """),
            conn
        )
    for col in [
        "monto_original",
        "monto_total_credito",
        "valor_cuota",
        "total_pagado",
        "saldo",
        "saldo_capital",
        "tasa_mensual",
        "interes_acumulado"
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

@st.cache_data(ttl=45, show_spinner=False)
def load_mora():
    with get_conn() as conn:
        mora_df = pd.read_sql(text("""
            WITH interes_libre AS (
                SELECT
                    p.id,
                    COALESCE(p.interes_acumulado, 0) + ROUND(COALESCE(p.saldo_capital, p.monto_original) * COALESCE(p.tasa_mensual, 0), 2) AS valor,
                    COALESCE(
                        NULLIF(p.fecha_proximo_interes::text, '')::date,
                        (COALESCE(NULLIF(p.fecha_desembolso::text, ''), NULLIF(p.fecha_inicio::text, ''))::date + INTERVAL '30 day')::date
                    ) AS fecha_vencimiento
                FROM prestamos p
                WHERE (LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) = 'interes_libre' OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre') OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre'))
                  AND LOWER(TRIM(COALESCE(p.estado, ''))) = 'activo'
                  AND COALESCE(p.contrato_aceptado, 0) = 1
                  AND COALESCE(p.contrato_cancelado, 0) = 0
            ),
            mora_base AS (
                SELECT cu.prestamo_id, COALESCE(cu.valor_cuota, 0) AS valor
                FROM cuotas cu
                JOIN prestamos p ON p.id = cu.prestamo_id
                WHERE cu.estado <> 'Pagada'
                  AND cu.fecha_vencimiento::date < :hoy
                  AND LOWER(TRIM(COALESCE(p.estado, ''))) = 'activo'
                  AND COALESCE(p.contrato_aceptado, 0) = 1
                  AND COALESCE(p.contrato_cancelado, 0) = 0
                  AND NOT (LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) = 'interes_libre' OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre') OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre'))
                UNION ALL
                SELECT id AS prestamo_id, valor
                FROM interes_libre
                WHERE fecha_vencimiento < :hoy
            )
            SELECT
                COUNT(DISTINCT prestamo_id) as clientes_mora,
                COALESCE(SUM(valor),0) as monto_mora
            FROM mora_base
        """), conn, params={"hoy": hoy_local().isoformat()})
    if mora_df.empty:
        return 0, 0.0
    return int(mora_df["clientes_mora"][0] or 0), float(mora_df["monto_mora"][0] or 0)

@st.cache_data(ttl=45, show_spinner=False)
def load_detalle_mora():
    with get_conn() as conn:
        return pd.read_sql(text("""
            WITH interes_libre AS (
                SELECT
                    p.id,
                    c.nombres || ' ' || c.apellidos AS cliente,
                    COALESCE(p.interes_acumulado, 0) + ROUND(COALESCE(p.saldo_capital, p.monto_original) * COALESCE(p.tasa_mensual, 0), 2) AS monto_en_mora,
                    COALESCE(p.saldo_capital, p.monto_original) AS exposicion_en_mora,
                    COALESCE(
                        NULLIF(p.fecha_proximo_interes::text, '')::date,
                        (COALESCE(NULLIF(p.fecha_desembolso::text, ''), NULLIF(p.fecha_inicio::text, ''))::date + INTERVAL '30 day')::date
                    ) AS fecha_vencimiento
                FROM prestamos p
                JOIN clientes c ON c.cedula = p.cliente_cedula
                WHERE (LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) = 'interes_libre' OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre') OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre'))
                  AND (LOWER(TRIM(COALESCE(p.estado, ''))) = 'activo' OR COALESCE(p.contrato_aceptado, 0) = 1)
                  AND COALESCE(p.contrato_cancelado, 0) = 0
            )
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
              AND cu.fecha_vencimiento::date < :hoy
              AND (LOWER(TRIM(COALESCE(p.estado, ''))) = 'activo' OR COALESCE(p.contrato_aceptado, 0) = 1)
              AND COALESCE(p.contrato_cancelado, 0) = 0
              AND NOT (LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) = 'interes_libre' OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre') OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre'))
            GROUP BY p.id, c.nombres, c.apellidos
            UNION ALL
            SELECT
                id,
                cliente,
                1 AS cuotas_en_mora,
                monto_en_mora,
                exposicion_en_mora
            FROM interes_libre
            WHERE fecha_vencimiento < :hoy
        """), conn, params={"hoy": hoy_local().isoformat()})

@st.cache_data(ttl=45, show_spinner=False)
def load_cuotas_periodo(inicio_iso, fin_iso):
    with get_conn() as conn:
        return pd.read_sql(text("""
            WITH interes_libre AS (
                SELECT
                    COALESCE(
                        NULLIF(p.fecha_proximo_interes::text, '')::date,
                        (COALESCE(NULLIF(p.fecha_inicio::text, ''), NULLIF(p.fecha_desembolso::text, ''))::date + INTERVAL '30 day')::date
                    ) AS fecha_vencimiento,
                    COALESCE(p.interes_acumulado, 0) + ROUND(COALESCE(p.saldo_capital, p.monto_original) * COALESCE(p.tasa_mensual, 0), 2) AS valor_cuota,
                    'Pendiente' AS estado,
                    0 AS nro_cuota,
                    p.id AS credito,
                    COALESCE(p.estado, '') AS estado_credito,
                    COALESCE(p.contrato_cancelado, 0) AS contrato_cancelado,
                    'Interés libre' AS tipo_credito,
                    c.nombres || ' ' || c.apellidos AS cliente
                FROM prestamos p
                JOIN clientes c ON c.cedula = p.cliente_cedula
                WHERE (
                    LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                )
                  AND (LOWER(TRIM(COALESCE(p.estado, ''))) = 'activo' OR COALESCE(p.contrato_aceptado, 0) = 1)
                  AND COALESCE(p.contrato_cancelado, 0) = 0
                  AND COALESCE(p.saldo_capital, p.monto_original, 0) > 0
            )
            SELECT
                cu.fecha_vencimiento::date AS fecha_vencimiento,
                cu.valor_cuota,
                cu.estado,
                cu.nro_cuota,
                p.id AS credito,
                COALESCE(p.estado, '') AS estado_credito,
                COALESCE(p.contrato_cancelado, 0) AS contrato_cancelado,
                COALESCE(p.tipo, 'Normal') AS tipo_credito,
                c.nombres || ' ' || c.apellidos AS cliente
            FROM cuotas cu
            JOIN prestamos p ON p.id = cu.prestamo_id
            JOIN clientes c ON c.cedula = p.cliente_cedula
            WHERE cu.fecha_vencimiento::date >= :inicio
              AND cu.fecha_vencimiento::date <= :fin
              AND (LOWER(TRIM(COALESCE(p.estado, ''))) = 'activo' OR COALESCE(p.contrato_aceptado, 0) = 1)
              AND COALESCE(p.contrato_cancelado, 0) = 0
              AND NOT (
                    LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                )
            UNION ALL
            SELECT
                fecha_vencimiento,
                valor_cuota,
                estado,
                nro_cuota,
                credito,
                estado_credito,
                contrato_cancelado,
                tipo_credito,
                cliente
            FROM interes_libre
            WHERE fecha_vencimiento >= :inicio
              AND fecha_vencimiento <= :fin
            ORDER BY fecha_vencimiento, cliente
        """), conn, params={"inicio": inicio_iso, "fin": fin_iso})

@st.cache_data(ttl=45, show_spinner=False)
def load_cuotas_proyeccion(inicio_iso, fin_iso):
    with get_conn() as conn:
        return pd.read_sql(text("""
            WITH interes_libre AS (
                SELECT
                    COALESCE(
                        NULLIF(p.fecha_proximo_interes::text, '')::date,
                        (COALESCE(NULLIF(p.fecha_inicio::text, ''), NULLIF(p.fecha_desembolso::text, ''))::date + INTERVAL '30 day')::date
                    ) AS fecha_vencimiento,
                    COALESCE(p.interes_acumulado, 0) + ROUND(COALESCE(p.saldo_capital, p.monto_original) * COALESCE(p.tasa_mensual, 0), 2) AS valor_cuota,
                    'Pendiente' AS estado_cuota,
                    0 AS nro_cuota,
                    p.id AS credito,
                    COALESCE(p.estado, '') AS estado_credito,
                    COALESCE(p.contrato_cancelado, 0) AS contrato_cancelado,
                    'Interés libre' AS tipo_credito,
                    c.nombres || ' ' || c.apellidos AS cliente
                FROM prestamos p
                JOIN clientes c ON c.cedula = p.cliente_cedula
                WHERE (
                    LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                )
                  AND (LOWER(TRIM(COALESCE(p.estado, ''))) = 'activo' OR COALESCE(p.contrato_aceptado, 0) = 1)
                  AND COALESCE(p.contrato_cancelado, 0) = 0
                  AND COALESCE(p.saldo_capital, p.monto_original, 0) > 0
            )
            SELECT
                cu.fecha_vencimiento::date AS fecha_vencimiento,
                cu.valor_cuota,
                cu.estado AS estado_cuota,
                cu.nro_cuota,
                p.id AS credito,
                COALESCE(p.estado, '') AS estado_credito,
                COALESCE(p.contrato_cancelado, 0) AS contrato_cancelado,
                COALESCE(p.tipo, 'Normal') AS tipo_credito,
                c.nombres || ' ' || c.apellidos AS cliente
            FROM cuotas cu
            JOIN prestamos p ON p.id = cu.prestamo_id
            JOIN clientes c ON c.cedula = p.cliente_cedula
            WHERE cu.fecha_vencimiento::date >= :inicio
              AND cu.fecha_vencimiento::date <= :fin
              AND cu.estado <> 'Pagada'
              AND (LOWER(TRIM(COALESCE(p.estado, ''))) = 'activo' OR COALESCE(p.contrato_aceptado, 0) = 1)
              AND COALESCE(p.contrato_cancelado, 0) = 0
              AND NOT (
                    LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                )
            UNION ALL
            SELECT
                fecha_vencimiento,
                valor_cuota,
                estado_cuota,
                nro_cuota,
                credito,
                estado_credito,
                contrato_cancelado,
                tipo_credito,
                cliente
            FROM interes_libre
            WHERE fecha_vencimiento >= :inicio
              AND fecha_vencimiento <= :fin
            ORDER BY fecha_vencimiento, cliente
        """), conn, params={"inicio": inicio_iso, "fin": fin_iso})

@st.cache_data(ttl=45, show_spinner=False)
def load_kpis_financieros():
    with get_conn() as conn:
        row = conn.execute(text("""
            WITH prestamos_financieros AS (
                SELECT *
                FROM prestamos
                WHERE LOWER(TRIM(COALESCE(estado, ''))) <> 'anulado'
                  AND COALESCE(contrato_cancelado, 0) = 0
                  AND (
                      COALESCE(contrato_aceptado, 0) = 1
                      OR LOWER(TRIM(COALESCE(estado, ''))) IN ('activo', 'cancelado')
                  )
            ),
            prestamos_activos AS (
                SELECT *
                FROM prestamos_financieros
                WHERE LOWER(TRIM(COALESCE(estado, ''))) = 'activo'
            ),
            pagos_financieros AS (
                SELECT
                    pg.id_pago,
                    pg.prestamo_id,
                    COALESCE(pg.valor, 0) AS valor,
                    COALESCE(pg.capital_pagado, 0) AS capital_pagado,
                    COALESCE(pg.interes_pagado, 0) AS interes_pagado,
                    COALESCE(pg.tipo_movimiento, 'CUOTA') AS tipo_movimiento
                FROM pagos pg
                JOIN prestamos_financieros pf ON pf.id = pg.prestamo_id
            ),
            intereses_libres_activos AS (
                SELECT
                    pa.id,
                    COALESCE(pa.saldo_capital, pa.monto_original) AS saldo_capital,
                    COALESCE(pa.interes_acumulado, 0) + ROUND(COALESCE(pa.saldo_capital, pa.monto_original) * COALESCE(pa.tasa_mensual, 0), 2) AS interes_pendiente,
                    COALESCE(
                        NULLIF(pa.fecha_proximo_interes::text, '')::date,
                        (COALESCE(NULLIF(pa.fecha_inicio::text, ''), NULLIF(pa.fecha_desembolso::text, ''))::date + INTERVAL '30 day')::date
                    ) AS fecha_proximo_interes
                FROM prestamos pa
                WHERE (
                    LOWER(TRANSLATE(TRIM(COALESCE(pa.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(pa.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(pa.tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                )
                  AND (LOWER(TRIM(COALESCE(pa.estado, ''))) = 'activo' OR COALESCE(pa.contrato_aceptado, 0) = 1)
                  AND COALESCE(pa.contrato_cancelado, 0) = 0
                  AND COALESCE(pa.saldo_capital, pa.monto_original, 0) > 0
            ),
            cuotas_pendientes AS (
                SELECT COALESCE(SUM(cu.valor_cuota), 0) AS total
                FROM cuotas cu
                JOIN prestamos_activos pa ON pa.id = cu.prestamo_id
                WHERE cu.estado <> 'Pagada'
                  AND COALESCE(pa.contrato_cancelado, 0) = 0
                  AND NOT (
                    LOWER(TRANSLATE(TRIM(COALESCE(pa.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(pa.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(pa.tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                )
            ),
            intereses_libres_pendientes AS (
                SELECT COALESCE(SUM(interes_pendiente), 0) AS total
                FROM intereses_libres_activos
            ),
            cartera_mora AS (
                SELECT COALESCE(SUM(total), 0) AS total
                FROM (
                    SELECT COALESCE(SUM(cu.valor_cuota), 0) AS total
                    FROM cuotas cu
                    JOIN prestamos_activos pa ON pa.id = cu.prestamo_id
                    WHERE cu.estado <> 'Pagada'
                      AND cu.fecha_vencimiento::date < :hoy
                      AND COALESCE(pa.contrato_cancelado, 0) = 0
                      AND NOT (
                    LOWER(TRANSLATE(TRIM(COALESCE(pa.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(pa.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(pa.tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                )
                    UNION ALL
                    SELECT COALESCE(SUM(interes_pendiente), 0) AS total
                    FROM intereses_libres_activos
                    WHERE fecha_proximo_interes < :hoy
                ) x
            ),
            contratos_pendientes AS (
                SELECT COUNT(*) AS total,
                       COALESCE(SUM(monto_original), 0) AS capital
                FROM prestamos
                WHERE LOWER(TRIM(COALESCE(estado, ''))) = 'pendiente'
                  AND COALESCE(contrato_aceptado, 0) = 0
                  AND COALESCE(contrato_cancelado, 0) = 0
            )
            SELECT
                COALESCE((SELECT SUM(monto_original) FROM prestamos_financieros), 0) AS capital_colocado,
                COALESCE((SELECT SUM(capital_pagado) FROM pagos_financieros), 0) AS capital_recuperado,
                COALESCE((SELECT SUM(interes_pagado) FROM pagos_financieros), 0) AS interes_cobrado,
                COALESCE((SELECT SUM(COALESCE(saldo_capital, monto_original)) FROM prestamos_activos), 0) AS capital_vivo,
                COALESCE((SELECT SUM(valor) FROM pagos_financieros), 0) AS recaudo_acumulado,
                COALESCE((SELECT total FROM cuotas_pendientes), 0) + COALESCE((SELECT total FROM intereses_libres_pendientes), 0) AS cuotas_pendientes,
                COALESCE((SELECT total FROM intereses_libres_pendientes), 0) AS interes_libre_pendiente,
                COALESCE((SELECT total FROM cartera_mora), 0) AS cartera_mora,
                COALESCE((SELECT COUNT(*) FROM prestamos_activos), 0) AS creditos_activos,
                COALESCE((SELECT total FROM contratos_pendientes), 0) AS contratos_pendientes,
                COALESCE((SELECT capital FROM contratos_pendientes), 0) AS capital_pendiente_aprobacion
        """), {"hoy": hoy_local().isoformat()}).mappings().first()

    data = dict(row or {})
    capital_colocado = float(data.get("capital_colocado", 0) or 0)
    capital_recuperado = float(data.get("capital_recuperado", 0) or 0)
    interes_cobrado = float(data.get("interes_cobrado", 0) or 0)
    capital_vivo = float(data.get("capital_vivo", 0) or 0)
    recaudo_acumulado = float(data.get("recaudo_acumulado", 0) or 0)

    data["diferencia_capital"] = round(capital_colocado - (capital_recuperado + capital_vivo), 2)
    data["diferencia_recaudo"] = round(recaudo_acumulado - (capital_recuperado + interes_cobrado), 2)
    data["recuperacion_capital_pct"] = round((capital_recuperado / capital_colocado) * 100, 2) if capital_colocado > 0 else 0.0
    data["margen_realizado_pct"] = round((interes_cobrado / capital_colocado) * 100, 2) if capital_colocado > 0 else 0.0
    data["mora_sobre_cuotas_pct"] = round((float(data.get("cartera_mora", 0) or 0) / float(data.get("cuotas_pendientes", 0) or 0)) * 100, 2) if float(data.get("cuotas_pendientes", 0) or 0) > 0 else 0.0
    data["consistencia_ok"] = abs(data["diferencia_capital"]) <= 1 and abs(data["diferencia_recaudo"]) <= 1
    return data

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
    clear_app_caches()
  
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
    :root{
        color-scheme: light;
        --login-bg: #f8fafc;
        --login-surface: #ffffff;
        --login-surface-soft: #fbfdff;
        --login-border: #e2e8f0;
        --login-border-strong: #dfe7f2;
        --login-text: #0f172a;
        --login-text-soft: #64748b;
        --login-label: #334155;
        --login-input-bg: #f8fafc;
        --login-note: #94a3b8;
        --login-chip-bg: #eff6ff;
        --login-chip-text: #2563eb;
        --login-chip-border: #dbeafe;
        --login-shadow: 0 26px 70px rgba(15,23,42,.10);
        --login-form-shadow: 0 12px 30px rgba(15,23,42,.06);
    }
    @media (prefers-color-scheme: dark){
        :root{
            color-scheme: dark;
            --login-bg: #020817;
            --login-surface: #0f172a;
            --login-surface-soft: #111827;
            --login-border: #334155;
            --login-border-strong: #334155;
            --login-text: #f8fafc;
            --login-text-soft: #cbd5e1;
            --login-label: #e2e8f0;
            --login-input-bg: #111827;
            --login-note: #94a3b8;
            --login-chip-bg: rgba(37,99,235,.14);
            --login-chip-text: #bfdbfe;
            --login-chip-border: rgba(147,197,253,.24);
            --login-shadow: 0 26px 70px rgba(2,6,23,.45);
            --login-form-shadow: 0 12px 30px rgba(2,6,23,.28);
        }
    }
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"]{
        background: var(--login-bg) !important;
    }
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
        background: linear-gradient(180deg, var(--login-surface) 0%, var(--login-surface-soft) 100%);
        border: 1px solid var(--login-border);
        border-radius: 30px;
        overflow: hidden;
        box-shadow: var(--login-shadow);
    }
    .login-stage::before{
        content: "";
        position: absolute;
        inset: 0;
        background: radial-gradient(circle at top right, rgba(37,99,235,.10), transparent 30%);
        pointer-events: none;
    }
    .login-head{
        padding: 20px 28px 14px 28px;
        background: var(--login-surface);
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
        color: var(--login-text);
    }
    .login-title-wrap p{
        margin:10px 0 0 0;
        font-size:20px;
        line-height:1.55;
        color: var(--login-text-soft);
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
        color: var(--login-chip-text);
        background: var(--login-chip-bg);
        border:1px solid var(--login-chip-border);
        border-radius:999px;
        padding:8px 13px;
        margin-bottom:16px;
        text-transform: uppercase;
    }
    .login-title{
        font-size:44px;
        line-height:1.04;
        font-weight:900;
        color: var(--login-text);
        margin:0 0 12px 0;
        letter-spacing:-.035em;
    }
    .login-sub{
        font-size:17px;
        line-height:1.72;
        color: var(--login-text-soft);
        margin:0 0 16px 0;
    }
    .login-note{
        text-align:center;
        color: var(--login-note);
        font-size:12.5px;
        margin-top:16px;
    }
    div[data-testid="stForm"]{
        border: 1px solid var(--login-border-strong) !important;
        border-radius: 22px !important;
        padding: 18px 18px 16px 18px !important;
        background: color-mix(in srgb, var(--login-surface) 94%, transparent) !important;
        box-shadow: var(--login-form-shadow) !important;
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
        border:1px solid var(--login-border) !important;
        background: var(--login-input-bg) !important;
        color: var(--login-text) !important;
        min-height: 52px !important;
        font-size:16px !important;
        padding-left: 14px !important;
    }
    .stTextInput > label{
        font-weight:700 !important;
        color: var(--login-label) !important;
    }
    .stTextInput input::placeholder{
        color: var(--login-text-soft) !important;
        opacity: .9 !important;
    }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button{
        border-radius: 14px !important;
        min-height: 54px !important;
        font-size: 17px !important;
        font-weight: 800 !important;
        border: 0 !important;
        color: #ffffff !important;
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


from contextlib import nullcontext

# ==========================
# NAVEGACIÓN LATERAL
# ==========================
MENU_LABELS = ["📊 Resumen"]
if PUEDE_VER_CLIENTES:
    MENU_LABELS.append("👥 Clientes")
if PUEDE_CREAR_CREDITOS:
    MENU_LABELS.append("🆕 Nuevo crédito")
if PUEDE_VER_DETALLE:
    MENU_LABELS.append("📄 Detalle por crédito")
if PUEDE_REGISTRAR_PAGOS:
    MENU_LABELS.append("💰 Pagos")
if PUEDE_USAR_SIMULADOR:
    MENU_LABELS.append("📈 Proyección")
    MENU_LABELS.append("🧮 Simulador")

if "menu_activo" not in st.session_state or st.session_state.menu_activo not in MENU_LABELS:
    st.session_state.menu_activo = MENU_LABELS[0]

st.markdown("""
<style>
[data-testid="stSidebar"]{
    background: linear-gradient(180deg, #07173c 0%, #081a44 42%, #0a1530 100%) !important;
    border-right: 1px solid rgba(96,165,250,.14);
}
[data-testid="stSidebar"] > div:first-child{
    padding-top: .45rem;
}
[data-testid="stSidebar"] *{
    color: #f8fafc;
}
.sidebar-logo-wrap{
    padding-top: .25rem;
    text-align: left;
}
.sidebar-brand{
    font-size: 28px;
    font-weight: 900;
    letter-spacing: -.03em;
    color: #ffffff;
    margin-top: 10px;
    line-height: 1.06;
}
.sidebar-brand-accent{
    color: #3b82f6;
}
.sidebar-sub{
    font-size: 12px;
    color: #cbd5e1;
    line-height: 1.5;
    margin: 10px 0 18px 0;
}
.sidebar-menu-title{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: #93c5fd;
    opacity: .9;
    margin: 10px 0 10px 2px;
}
[data-testid="stSidebar"] .stRadio > div{
    gap: .42rem !important;
}
[data-testid="stSidebar"] .stRadio label{
    position: relative;
    width: 100%;
    margin: 0;
    background: transparent !important;
    border: 1px solid transparent !important;
    border-radius: 16px !important;
    padding: 12px 14px 12px 16px !important;
    transition: all .18s ease;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stRadio label > div:first-child{
    display: none !important;
}
[data-testid="stSidebar"] .stRadio label p{
    color: #dbeafe !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    line-height: 1.15 !important;
}
[data-testid="stSidebar"] .stRadio label:hover{
    background: rgba(59,130,246,.10) !important;
    border-color: rgba(96,165,250,.26) !important;
    transform: translateX(2px);
}
[data-testid="stSidebar"] .stRadio label:has(input:checked){
    background: linear-gradient(135deg, rgba(29,78,216,.28) 0%, rgba(37,99,235,.18) 55%, rgba(59,130,246,.12) 100%) !important;
    border-color: rgba(96,165,250,.32) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.05), 0 10px 24px rgba(2,6,23,.20) !important;
}
[data-testid="stSidebar"] .stRadio label:has(input:checked)::before{
    content: "";
    position: absolute;
    left: 0;
    top: 8px;
    bottom: 8px;
    width: 4px;
    border-radius: 999px;
    background: linear-gradient(180deg, #22d3ee 0%, #3b82f6 100%);
}
.sidebar-user-card{
    margin-top: 20px;
    border: 1px solid rgba(96,165,250,.16);
    background: linear-gradient(180deg, rgba(255,255,255,.065) 0%, rgba(255,255,255,.04) 100%);
    border-radius: 20px;
    padding: 14px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.04);
}
.sidebar-user-top{
    display:flex;
    align-items:center;
    gap:12px;
    margin-bottom:10px;
}
.sidebar-avatar{
    width:44px;
    height:44px;
    border-radius:50%;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:18px;
    font-weight:900;
    color:#ffffff;
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 48%, #0ea5e9 100%);
    box-shadow: 0 10px 22px rgba(2,6,23,.24);
}
.sidebar-user-pill{
    display: inline-block;
    background: rgba(37,99,235,.18);
    border: 1px solid rgba(147,197,253,.20);
    border-radius: 999px;
    color: #dbeafe;
    font-size: 10px;
    font-weight: 800;
    padding: 4px 9px;
    margin-bottom: 4px;
}
.sidebar-user-name{
    font-size: 16px;
    font-weight: 800;
    color: #ffffff;
    line-height:1.1;
}
.sidebar-user-role{
    font-size: 12px;
    color: #bfdbfe;
    margin-top: 3px;
}
[data-testid="stSidebar"] div.stButton > button{
    width: 100%;
    border-radius: 15px !important;
    min-height: 46px !important;
    font-weight: 800 !important;
    border: 1px solid rgba(96,165,250,.20) !important;
    color: #ffffff !important;
    background: linear-gradient(135deg, #163f97 0%, #1d4ed8 48%, #2563eb 100%) !important;
    box-shadow: 0 14px 28px rgba(2,6,23,.24) !important;
    margin-top: 6px;
}
[data-testid="stSidebar"] div.stButton > button:hover{
    transform: translateY(-1px);
    box-shadow: 0 16px 30px rgba(2,6,23,.28) !important;
}
.sidebar-foot{
    text-align:center;
    color:#93a7cf;
    font-size:11px;
    margin-top:10px;
    opacity:.92;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div class='sidebar-logo-wrap'>", unsafe_allow_html=True)
    if os.path.exists("logo_creddt.png"):
        st.image("logo_creddt.png", width=112)
    st.markdown("<div class='sidebar-brand'>CREDDT | <span class='sidebar-brand-accent'>CRNTECH</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-sub'>Gestión principal de créditos, clientes, pagos y seguimiento operativo.</div>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-menu-title'>Menú principal</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.session_state.menu_activo = st.radio(
        "Opciones",
        MENU_LABELS,
        index=MENU_LABELS.index(st.session_state.menu_activo),
        label_visibility="collapsed"
    )

    st.markdown(
        f"<div class='sidebar-user-card'>"
        f"<div class='sidebar-user-top'>"
        f"<div class='sidebar-avatar'>👤</div>"
        f"<div>"
        f"<div class='sidebar-user-pill'>Sesión activa</div>"
        f"<div class='sidebar-user-name'>{st.session_state.get('usuario','-')}</div>"
        f"<div class='sidebar-user-role'>Rol: {st.session_state.get('rol','-')}</div>"
        f"</div>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True
    )

    if st.button("↪ Cerrar sesión", key="btn_logout_sidebar"):
        for k in ["auth", "usuario", "rol", "menu_activo", "pago_msg", "detalle", "detalle_mora"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    st.markdown("<div class='sidebar-foot'>v1.0.0 • CREDDT | CRNTECH</div>", unsafe_allow_html=True)

SECCION_ACTIVA = st.session_state.menu_activo

# ==========================
# HEADER - TITULO
# ==========================
st.markdown("""
<style>
:root{
    --app-bg: #f8fafc;
    --surface: #ffffff;
    --surface-soft: #f8fafc;
    --surface-accent: #eff6ff;
    --border-color: #e2e8f0;
    --text-primary: #0f172a;
    --text-secondary: #64748b;
    --text-tertiary: #475569;
    --chip-text: #1d4ed8;
    --card-bg: #ffffff;
    --card-border: #e2e8f0;
    --status-paid-bg: #dcfce7;
    --status-paid-text: #166534;
    --status-partial-bg: #fef3c7;
    --status-partial-text: #92400e;
    --status-pending-bg: #fee2e2;
    --status-pending-text: #991b1b;
}
@media (prefers-color-scheme: dark){
    :root{
        --app-bg: #0b1220;
        --surface: #111827;
        --surface-soft: #0f172a;
        --surface-accent: #172554;
        --border-color: #334155;
        --text-primary: #f8fafc;
        --text-secondary: #cbd5e1;
        --text-tertiary: #e2e8f0;
        --chip-text: #bfdbfe;
        --card-bg: #111827;
        --card-border: #334155;
        --status-paid-bg: rgba(22,101,52,.22);
        --status-paid-text: #bbf7d0;
        --status-partial-bg: rgba(146,64,14,.26);
        --status-partial-text: #fde68a;
        --status-pending-bg: rgba(153,27,27,.24);
        --status-pending-text: #fecaca;
    }
}
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"]{
    background: var(--app-bg) !important;
}
.home-hero-wrap{
    padding-top: .15rem;
    padding-bottom: .2rem;
}
.home-title{
    margin: 0 !important;
    color: var(--text-primary);
    font-size:42px;
    line-height:1.04;
    font-weight:900;
    letter-spacing:-.03em;
    text-align:center;
}
.home-subtitle{
    margin-top:8px;
    color: var(--text-secondary);
    font-size:16px;
    line-height:1.55;
    text-align:center;
    font-weight:500;
}
.home-chip{
    display:inline-block;
    background: var(--surface-accent);
    color: var(--chip-text);
    border:1px solid var(--border-color);
    border-radius:999px;
    padding:8px 12px;
    font-size:12px;
    font-weight:800;
    margin-left:8px;
    margin-top:6px;
    white-space:nowrap;
}
.home-blue-line{
    height: 10px;
    width: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #081a44 0%, #173266 48%, #2563eb 100%);
    box-shadow: 0 10px 22px rgba(15,23,42,.12);
    margin: 14px 0 10px 0;
}
.creddt-card{
    background: var(--surface);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: 16px;
}
.creddt-soft-card{
    background: var(--surface-soft);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: 16px;
}
.creddt-muted{
    color: var(--text-secondary);
}
.creddt-strong{
    color: var(--text-primary);
}
.cuota-card{
    background: var(--card-bg) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 16px;
    padding: 14px 15px;
    margin-bottom: 14px;
    box-shadow: 0 8px 20px rgba(15,23,42,.07);
    min-height: 142px;
}
.cuota-card-title{
    color: var(--text-primary) !important;
    font-weight: 800;
    font-size: 15px;
    line-height: 1.25;
    word-break: break-word;
}
.cuota-card-meta{
    color: var(--text-secondary) !important;
    font-size: 13px;
    margin-top: 6px;
    line-height: 1.35;
}
.cuota-card-value{
    color: var(--text-primary) !important;
    font-size: 18px;
    font-weight: 900;
    margin-top: 9px;
}
.cuota-status{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border-radius: 999px;
    padding: 6px 10px;
    margin-top: 8px;
    font-size: 12px;
    font-weight: 800;
}
.cuota-status-pagada{
    background: var(--status-paid-bg);
    color: var(--status-paid-text);
}
.cuota-status-parcial{
    background: var(--status-partial-bg);
    color: var(--status-partial-text);
}
.cuota-status-pendiente{
    background: var(--status-pending-bg);
    color: var(--status-pending-text);
}
@media (max-width: 1024px) {
  div[data-testid="stHorizontalBlock"] {
    gap: .75rem !important;
    flex-wrap: wrap !important;
  }
}
@media (max-width: 768px) {
  .home-title{
    font-size:30px !important;
    text-align:left !important;
  }
  .home-subtitle{
    font-size:14px !important;
    text-align:left !important;
  }
  .home-chip{
    margin-left:0 !important;
    margin-right:8px !important;
  }
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
  .cuota-card{
    min-height: auto !important;
    padding: 14px !important;
  }
  .cuota-card-title{
    font-size: 15px !important;
  }
  .cuota-card-value{
    font-size: 17px !important;
  }
}
</style>
""", unsafe_allow_html=True)

usuario_hdr = st.session_state.get("usuario", "-")
rol_hdr = st.session_state.get("rol", "-")

with st.container():
    st.markdown("<div class='home-hero-wrap'></div>", unsafe_allow_html=True)
    col_logo, col_centro, col_derecha = st.columns([1.15, 4.4, 2.2], gap="small")
    with col_logo:
        st.image("logo_creddt.png", width=138)
    with col_centro:
        st.markdown("<div class='home-title'>CREDDT | CRNTECH</div>", unsafe_allow_html=True)
        st.markdown("<div class='home-subtitle'>Plataforma inteligente de gestión de créditos</div>", unsafe_allow_html=True)
    with col_derecha:
        st.markdown(
            f"<div style='text-align:right; padding-top:12px;'>"
            f"<span class='home-chip'>Usuario: <strong>{usuario_hdr}</strong></span>"
            f"<span class='home-chip'>Rol: <strong>{rol_hdr}</strong></span>"
            f"</div>",
            unsafe_allow_html=True
        )

st.markdown("<div class='home-blue-line'></div>", unsafe_allow_html=True)

if st.session_state.get("app_busy") and st.session_state.get("app_busy_label"):
    st.info(f"⏳ {st.session_state.get('app_busy_label')}")
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
                tipo_credito TEXT DEFAULT 'normal',
                saldo_capital NUMERIC(18,2),
                tasa_mensual NUMERIC(12,6),
                interes_acumulado NUMERIC(18,2) DEFAULT 0,
                fecha_ultimo_corte_interes TEXT,
                fecha_proximo_interes TEXT,
                fecha_cierre_manual TEXT,
                contrato_aceptado INTEGER DEFAULT 0,
                contrato_token TEXT,
                fecha_aceptacion TEXT,
                fecha_desembolso TEXT,
                contrato_enviado INTEGER DEFAULT 0,
                fecha_envio_contrato TEXT,
                desembolso_notificado INTEGER DEFAULT 0,
                fecha_inicio TEXT,
                contrato_cancelado INTEGER DEFAULT 0,
                fecha_cancelacion_contrato TEXT,
                motivo_cancelacion_contrato TEXT,
                cancelado_por TEXT,
                FOREIGN KEY(cliente_cedula) REFERENCES clientes(cedula)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS auditoria_contratos (
                id SERIAL PRIMARY KEY,
                prestamo_id TEXT,
                accion TEXT,
                motivo TEXT,
                usuario TEXT,
                fecha TEXT,
                detalle TEXT
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
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS tipo_credito TEXT DEFAULT 'normal'",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS interes_acumulado NUMERIC(18,2) DEFAULT 0",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_ultimo_corte_interes TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_proximo_interes TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_cierre_manual TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS contrato_aceptado INTEGER DEFAULT 0",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS contrato_token TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_aceptacion TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_desembolso TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS contrato_enviado INTEGER DEFAULT 0",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_envio_contrato TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS desembolso_notificado INTEGER DEFAULT 0",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_inicio TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS contrato_cancelado INTEGER DEFAULT 0",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_cancelacion_contrato TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS motivo_cancelacion_contrato TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS cancelado_por TEXT",
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
                tipo_credito = COALESCE(tipo_credito, CASE WHEN LOWER(TRIM(COALESCE(tipo, ''))) = 'express' THEN 'express' ELSE 'normal' END),
                interes_acumulado = COALESCE(interes_acumulado, 0),
                contrato_aceptado = COALESCE(contrato_aceptado, 0),
                contrato_enviado = COALESCE(contrato_enviado, 0),
                desembolso_notificado = COALESCE(desembolso_notificado, 0),
                contrato_cancelado = COALESCE(contrato_cancelado, 0),
                fecha_inicio = COALESCE(fecha_inicio, :hoy),
                frecuencia = COALESCE(frecuencia, 'Mensual')
            WHERE saldo_capital IS NULL
               OR tasa_mensual IS NULL
               OR tipo_credito IS NULL
               OR interes_acumulado IS NULL
               OR contrato_aceptado IS NULL
               OR contrato_enviado IS NULL
               OR desembolso_notificado IS NULL
               OR contrato_cancelado IS NULL
               OR fecha_inicio IS NULL
               OR frecuencia IS NULL
        """), {"hoy": hoy_local().isoformat()})
        conn.commit()
    clear_app_caches()
asegurar_estructura_base()
def asegurar_estructura_financiera():
    with get_conn() as conn:
        sentencias = [
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS saldo_capital NUMERIC(18,2)",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS tasa_mensual NUMERIC(12,6)",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS tipo_credito TEXT DEFAULT 'normal'",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS interes_acumulado NUMERIC(18,2) DEFAULT 0",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_ultimo_corte_interes TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_proximo_interes TEXT",
            "ALTER TABLE prestamos ADD COLUMN IF NOT EXISTS fecha_cierre_manual TEXT",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS tipo_movimiento TEXT",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS detalle TEXT",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS interes_pagado NUMERIC(18,2)",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS capital_pagado NUMERIC(18,2)",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS saldo_capital_anterior NUMERIC(18,2)",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS saldo_capital_nuevo NUMERIC(18,2)",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS cuota_numero INTEGER",
            "ALTER TABLE pagos_cuotas ADD COLUMN IF NOT EXISTS valor_aplicado NUMERIC(18,2)"
        ]
        for sentencia in sentencias:
            conn.execute(text(sentencia))
        conn.execute(text("""
            UPDATE prestamos
            SET saldo_capital = COALESCE(saldo_capital, monto_original),
                tasa_mensual = COALESCE(tasa_mensual, 0),
                tipo_credito = COALESCE(
                    tipo_credito,
                    CASE
                        WHEN LOWER(TRIM(COALESCE(tipo, ''))) = 'express' THEN 'express'
                        WHEN LOWER(TRIM(COALESCE(tipo, ''))) IN ('interes libre', 'interés libre') THEN 'interes_libre'
                        ELSE 'normal'
                    END
                ),
                interes_acumulado = COALESCE(interes_acumulado, 0)
            WHERE saldo_capital IS NULL OR tasa_mensual IS NULL OR tipo_credito IS NULL OR interes_acumulado IS NULL
        """))
        conn.execute(text("""
            UPDATE prestamos
            SET tipo_credito = 'interes_libre',
                frecuencia = COALESCE(frecuencia, 'Mensual'),
                cuotas = COALESCE(cuotas, 0),
                fecha_ultimo_corte_interes = COALESCE(fecha_ultimo_corte_interes, fecha_desembolso, fecha_inicio),
                fecha_proximo_interes = COALESCE(
                    fecha_proximo_interes,
                    ((COALESCE(NULLIF(fecha_desembolso, ''), NULLIF(fecha_inicio, ''))::date + INTERVAL '30 day')::date)::text
                ),
                valor_cuota = COALESCE(valor_cuota, ROUND(COALESCE(saldo_capital, monto_original) * COALESCE(tasa_mensual, 0), 2))
            WHERE (LOWER(REPLACE(REPLACE(TRIM(COALESCE(tipo_credito, '')), 'é', 'e'), 'É', 'e')) = 'interes_libre' OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(tipo_credito, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre') OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(tipo, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre'))
              AND COALESCE(contrato_cancelado, 0) = 0
              AND LOWER(TRIM(COALESCE(estado, ''))) NOT IN ('anulado', 'cancelado')
              AND COALESCE(NULLIF(fecha_desembolso, ''), NULLIF(fecha_inicio, '')) IS NOT NULL
        """))
        conn.commit()
    clear_app_caches()
asegurar_estructura_financiera()

def limpiar_cuotas_creditos_no_vigentes():
    with get_conn() as conn:
        conn.execute(text("""
            UPDATE cuotas cu
            SET estado = 'Anulada'
            FROM prestamos p
            WHERE p.id = cu.prestamo_id
              AND cu.estado IN ('Pendiente', 'Parcial')
              AND (
                    LOWER(TRIM(COALESCE(p.estado, ''))) IN ('anulado', 'cancelado')
                    OR COALESCE(p.contrato_cancelado, 0) = 1
              )
        """))
        conn.commit()
    clear_app_caches()

limpiar_cuotas_creditos_no_vigentes()


def normalizar_fechas_interes_libre_aceptados():
    """Normaliza datos base de Interés libre sin crear cuotas."""
    try:
        with get_conn() as conn:
            conn.execute(text("""
                UPDATE prestamos
                SET tipo_credito = 'interes_libre',
                    tipo = 'Interés Libre',
                    estado = CASE
                        WHEN LOWER(TRIM(COALESCE(estado, ''))) = 'cancelado'
                             AND COALESCE(saldo_capital, monto_original, 0) > 0
                             AND fecha_cierre_manual IS NULL
                        THEN 'Activo'
                        ELSE estado
                    END,
                    saldo_capital = COALESCE(saldo_capital, monto_original),
                    interes_acumulado = COALESCE(interes_acumulado, 0),
                    fecha_inicio = COALESCE(NULLIF(fecha_inicio::text, ''), NULLIF(fecha_desembolso::text, ''), NULLIF(fecha_aceptacion::text, ''), CURRENT_DATE::text),
                    fecha_proximo_interes = COALESCE(
                        NULLIF(fecha_proximo_interes::text, ''),
                        (COALESCE(NULLIF(fecha_inicio::text, ''), NULLIF(fecha_desembolso::text, ''), NULLIF(fecha_aceptacion::text, ''), CURRENT_DATE::text)::date + INTERVAL '30 day')::date::text
                    ),
                    valor_cuota = ROUND(COALESCE(saldo_capital, monto_original) * COALESCE(tasa_mensual, 0), 2)
                WHERE (
                    LOWER(TRANSLATE(TRIM(COALESCE(tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                )
                  AND LOWER(TRIM(COALESCE(estado, ''))) <> 'anulado'
                  AND COALESCE(contrato_cancelado, 0) = 0
            """))
            conn.commit()
    except Exception:
        pass

def asegurar_estructura_control_financiero():
    with get_conn() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_meta (
                clave TEXT PRIMARY KEY,
                valor TEXT,
                updated_at TEXT
            )
        """))
        conn.commit()


def get_app_meta(clave, default=None):
    with get_conn() as conn:
        row = conn.execute(text("SELECT valor FROM app_meta WHERE clave = :clave"), {"clave": clave}).fetchone()
    return row[0] if row else default


def set_app_meta(conn, clave, valor):
    conn.execute(text("""
        INSERT INTO app_meta (clave, valor, updated_at)
        VALUES (:clave, :valor, :updated_at)
        ON CONFLICT (clave) DO UPDATE SET
            valor = EXCLUDED.valor,
            updated_at = EXCLUDED.updated_at
    """), {"clave": clave, "valor": str(valor), "updated_at": ahora_local().isoformat(timespec='seconds')})


def reconstruir_historial_financiero():
    resumen = {"prestamos": 0, "pagos": 0, "ajustes_negativos": 0}
    asegurar_estructura_control_financiero()
    with get_conn() as conn:
        prestamos = conn.execute(text("""
            SELECT id, monto_original, COALESCE(tasa_mensual, 0) AS tasa_mensual,
                   COALESCE(estado, '') AS estado, COALESCE(contrato_aceptado, 0) AS contrato_aceptado
            FROM prestamos
            WHERE COALESCE(estado, '') <> 'Anulado'
            ORDER BY id
        """)).mappings().all()

        for prestamo in prestamos:
            resumen["prestamos"] += 1
            saldo_actual = normalizar_decimal(prestamo["monto_original"])
            tasa_mensual = Decimal(str(prestamo["tasa_mensual"] or 0)).quantize(Decimal("0.000001"))
            pagos = conn.execute(text("""
                SELECT id_pago, fecha_pago, COALESCE(valor, 0) AS valor,
                       COALESCE(tipo_movimiento, '') AS tipo_movimiento,
                       COALESCE(detalle, '') AS detalle, cuota_numero
                FROM pagos
                WHERE prestamo_id = :prestamo_id
                ORDER BY COALESCE(fecha_pago, '1900-01-01'), id_pago
            """), {"prestamo_id": prestamo["id"]}).mappings().all()

            pago_cuota_map = {row[0]: row[1] for row in conn.execute(text("""
                SELECT pc.id_pago, cu.nro_cuota
                FROM pagos_cuotas pc
                JOIN cuotas cu ON cu.id_cuota = pc.id_cuota
                WHERE cu.prestamo_id = :prestamo_id
            """), {"prestamo_id": prestamo["id"]}).fetchall()}

            contador_cuotas = 0
            for pago in pagos:
                resumen["pagos"] += 1
                valor_pago = normalizar_decimal(pago["valor"])
                tipo_movimiento = (pago["tipo_movimiento"] or "").strip().upper()
                detalle = (pago["detalle"] or "").upper()
                if not tipo_movimiento:
                    tipo_movimiento = "ABONO_CAPITAL" if "ABONO" in detalle else "CUOTA"

                saldo_anterior = saldo_actual
                interes_pagado = Decimal("0.00")
                capital_pagado = Decimal("0.00")

                if valor_pago < 0:
                    resumen["ajustes_negativos"] += 1
                    capital_pagado = valor_pago
                    saldo_nuevo = saldo_anterior - capital_pagado
                elif tipo_movimiento == "ABONO_CAPITAL":
                    capital_pagado = min(valor_pago, saldo_anterior)
                    saldo_nuevo = saldo_anterior - capital_pagado
                else:
                    interes_estimado = (saldo_anterior * tasa_mensual).quantize(Decimal("0.01")) if tasa_mensual > 0 else Decimal("0.00")
                    interes_pagado = min(valor_pago, interes_estimado)
                    capital_pagado = valor_pago - interes_pagado
                    if capital_pagado < 0:
                        capital_pagado = Decimal("0.00")
                        interes_pagado = valor_pago
                    if capital_pagado > saldo_anterior:
                        capital_pagado = saldo_anterior
                        interes_pagado = valor_pago - capital_pagado
                        if interes_pagado < 0:
                            interes_pagado = Decimal("0.00")
                    saldo_nuevo = saldo_anterior - capital_pagado
                    contador_cuotas += 1

                if saldo_nuevo < 0:
                    saldo_nuevo = Decimal("0.00")

                cuota_numero = pago["cuota_numero"] or pago_cuota_map.get(pago["id_pago"])
                if not cuota_numero and tipo_movimiento != "ABONO_CAPITAL":
                    cuota_numero = contador_cuotas

                conn.execute(text("""
                    UPDATE pagos
                    SET tipo_movimiento = :tipo_movimiento,
                        interes_pagado = :interes_pagado,
                        capital_pagado = :capital_pagado,
                        saldo_capital_anterior = :saldo_capital_anterior,
                        saldo_capital_nuevo = :saldo_capital_nuevo,
                        cuota_numero = :cuota_numero
                    WHERE id_pago = :id_pago
                """), {
                    "id_pago": pago["id_pago"],
                    "tipo_movimiento": tipo_movimiento,
                    "interes_pagado": interes_pagado,
                    "capital_pagado": capital_pagado,
                    "saldo_capital_anterior": saldo_anterior,
                    "saldo_capital_nuevo": saldo_nuevo,
                    "cuota_numero": cuota_numero
                })

                saldo_actual = saldo_nuevo

            conn.execute(text("UPDATE prestamos SET saldo_capital = :saldo_capital WHERE id = :prestamo_id"), {
                "prestamo_id": prestamo["id"],
                "saldo_capital": saldo_actual
            })

            if prestamo["estado"] not in ("Pendiente", "Anulado"):
                pendientes = conn.execute(text("""
                    SELECT COUNT(*)
                    FROM cuotas
                    WHERE prestamo_id = :prestamo_id AND estado <> 'Pagada'
                """), {"prestamo_id": prestamo["id"]}).scalar()
                nuevo_estado = "Cancelado" if int(pendientes or 0) == 0 else "Activo"
                conn.execute(text("UPDATE prestamos SET estado = :estado WHERE id = :prestamo_id"), {
                    "prestamo_id": prestamo["id"],
                    "estado": nuevo_estado
                })

        set_app_meta(conn, "finanzas_reconciliadas_at", ahora_local().isoformat(timespec='seconds'))
        conn.commit()

    clear_app_caches()
    return resumen

asegurar_estructura_control_financiero()

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


def es_credito_interes_libre_valor(tipo_credito, tipo):
    tipo_credito_norm = str(tipo_credito or "").strip().lower()
    tipo_norm = str(tipo or "").strip().lower().replace("é", "e")
    return tipo_credito_norm == "interes_libre" or tipo_norm in ["interes libre", "solo interes libre"]


def es_credito_interes_libre_row(row):
    if row is None:
        return False
    getter = row.get if hasattr(row, "get") else lambda key, default=None: getattr(row, key, default)
    return es_credito_interes_libre_valor(getter("tipo_credito", getter("tipo_credito_codigo", "")), getter("tipo", ""))


def tasa_pct(tasa_mensual):
    try:
        return f"{float(tasa_mensual or 0) * 100:.2f}%"
    except Exception:
        return "0.00%"
def enviar_correo(destino, asunto, cuerpo):
    ok, error = enviar_correo_async(
        destino=destino,
        asunto=asunto,
        cuerpo=cuerpo
    )
    if not ok:
        st.warning(f"⚠️ El correo no pudo enviarse: {error}")
    return ok, error
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
        "CIERRE_CREDITO": "Área Administrativa y Financiera",
    }.get(tipo_correo, "Área Administrativa y Financiera")


def _titulo_correo(tipo_correo):
    return {
        "CONTRATO": "Aceptación de contrato de crédito",
        "DESEMBOLSO": "Confirmación de activación y desembolso",
        "RECORDATORIO": "Recordatorio de pago",
        "RECIBO_CUOTA": "Confirmación de pago recibido",
        "RECIBO_ABONO": "Confirmación de abono a capital",
        "CIERRE_CREDITO": "Crédito finalizado y cuenta cerrada",
    }.get(tipo_correo, "Notificación de crédito")


def _intro_correo(tipo_correo):
    return {
        "CONTRATO": "Adjuntamos el contrato de su crédito para revisión y aceptación. Este documento contiene el resumen aprobado de la operación y sus condiciones generales.",
        "DESEMBOLSO": "Le confirmamos que su contrato fue aceptado correctamente y que su crédito quedó activo para continuar el proceso operativo del desembolso.",
        "RECORDATORIO": "Le recordamos oportunamente la información de su obligación para facilitar la gestión de pago y mantener su crédito al día.",
        "RECIBO_CUOTA": "Le confirmamos que el pago de su cuota fue registrado exitosamente en nuestro sistema. Adjuntamos el comprobante para su soporte.",
        "RECIBO_ABONO": "Le confirmamos que su abono a capital fue registrado exitosamente en nuestro sistema. Adjuntamos el comprobante para su soporte.",
        "CIERRE_CREDITO": "Le confirmamos que su crédito quedó pagado en su totalidad. La obligación queda cerrada en nuestro sistema.",
    }.get(tipo_correo, "Adjuntamos la información correspondiente a su crédito para consulta y soporte.")


def _resumen_items_correo(tipo_correo, **kwargs):
    tipo_credito = kwargs.get("tipo_credito") or kwargs.get("tipo") or "Normal"
    es_il = es_credito_interes_libre_valor(kwargs.get("tipo_credito_codigo") or kwargs.get("tipo_credito"), kwargs.get("tipo") or tipo_credito)
    if tipo_correo == "CONTRATO":
        if es_il:
            return [
                ("Crédito", kwargs.get("prestamo_id")),
                ("Tipo de crédito", tipo_credito),
                ("Capital aprobado", pesos(kwargs.get("monto"))),
                ("Tasa mensual aplicada", tasa_pct(kwargs.get("tasa_interes"))),
                ("Condición", "Este crédito no tiene cuotas de capital programadas"),
                ("Interés estimado cada 30 días", pesos(kwargs.get("valor_cuota"))),
                ("Próximo pago de interés", kwargs.get("fecha_proximo_interes")),
                ("Capital vigente", pesos(kwargs.get("saldo_capital") or kwargs.get("monto"))),
            ]
        return [
            ("Crédito", kwargs.get("prestamo_id")),
            ("Tipo de crédito", tipo_credito),
            ("Monto aprobado", pesos(kwargs.get("monto"))),
            ("Número de cuotas", kwargs.get("cuotas")),
            ("Valor de la cuota", pesos(kwargs.get("valor_cuota"))),
            ("Frecuencia", kwargs.get("frecuencia")),
            ("Tasa de interés", tasa_pct(kwargs.get("tasa_interes"))),
        ]
    if tipo_correo == "DESEMBOLSO":
        if es_il:
            return [
                ("Crédito", kwargs.get("prestamo_id")),
                ("Tipo de crédito", tipo_credito),
                ("Capital desembolsado", pesos(kwargs.get("monto"))),
                ("Saldo capital", pesos(kwargs.get("saldo_capital") or kwargs.get("monto"))),
                ("Tasa mensual aplicada", tasa_pct(kwargs.get("tasa_interes"))),
                ("Condición", "Este crédito no tiene cuotas de capital programadas"),
                ("Interés estimado cada 30 días", pesos(kwargs.get("valor_cuota"))),
                ("Próximo pago de interés", kwargs.get("fecha_proximo_interes")),
                ("Estado", kwargs.get("estado") or "Activo"),
            ]
        return [
            ("Crédito", kwargs.get("prestamo_id")),
            ("Tipo de crédito", tipo_credito),
            ("Monto aprobado", pesos(kwargs.get("monto"))),
            ("Interés aplicado", tasa_pct(kwargs.get("tasa_interes"))),
            ("Frecuencia", kwargs.get("frecuencia")),
            ("Número de cuotas", kwargs.get("cuotas")),
            ("Valor de la cuota", pesos(kwargs.get("valor_cuota"))),
            ("Saldo pendiente", pesos(kwargs.get("saldo_pendiente"))),
            ("Estado", kwargs.get("estado") or "Activo"),
        ]
    if tipo_correo == "RECORDATORIO":
        if es_il:
            return [
                ("Crédito", kwargs.get("prestamo_id")),
                ("Tipo de crédito", tipo_credito),
                ("Condición", "Este crédito no tiene cuotas de capital programadas"),
                ("Capital vigente", pesos(kwargs.get("saldo_capital"))),
                ("Tasa mensual aplicada", tasa_pct(kwargs.get("tasa_interes"))),
                ("Interés causado o pendiente", pesos(kwargs.get("interes_pendiente"))),
                ("Próximo pago de interés", kwargs.get("fecha_vencimiento") or kwargs.get("fecha_proximo_interes")),
                ("Total próximo corte", pesos(kwargs.get("valor"))),
                ("Capital pendiente para cancelar todo", pesos(kwargs.get("saldo_capital"))),
                ("Estado", kwargs.get("estado") or "Activo"),
            ]
        return [
            ("Crédito", kwargs.get("prestamo_id")),
            ("Tipo de crédito", tipo_credito),
            ("Cuota", kwargs.get("cuota_nro")),
            ("Fecha de vencimiento", kwargs.get("fecha_vencimiento")),
            ("Valor a pagar", pesos(kwargs.get("valor"))),
            ("Cuotas pendientes", kwargs.get("cuotas_pendientes")),
            ("Saldo pendiente", pesos(kwargs.get("saldo_pendiente"))),
            ("Estado", kwargs.get("estado") or "Activo"),
        ]
    if tipo_correo == "RECIBO_CUOTA":
        if es_il:
            return [
                ("Crédito", kwargs.get("prestamo_id")),
                ("Tipo de crédito", tipo_credito),
                ("Fecha de pago", kwargs.get("fecha_pago")),
                ("Valor pagado", pesos(kwargs.get("valor"))),
                ("Aplicado a interés", pesos(kwargs.get("interes_pagado"))),
                ("Aplicado a capital", pesos(kwargs.get("capital_pagado"))),
                ("Nuevo saldo capital", pesos(kwargs.get("saldo_capital"))),
                ("Nuevo interés acumulado", pesos(kwargs.get("interes_pendiente"))),
                ("Próxima fecha de interés", kwargs.get("fecha_proximo_interes")),
                ("Estado", kwargs.get("estado") or "Activo"),
            ]
        return [
            ("Crédito", kwargs.get("prestamo_id")),
            ("Tipo de crédito", tipo_credito),
            ("Cuota aplicada", kwargs.get("cuota_nro")),
            ("Fecha de pago", kwargs.get("fecha_pago")),
            ("Valor pagado", pesos(kwargs.get("valor"))),
            ("Cuotas pendientes actualizadas", kwargs.get("cuotas_pendientes")),
            ("Saldo pendiente actualizado", pesos(kwargs.get("saldo_pendiente"))),
        ]
    if tipo_correo == "RECIBO_ABONO":
        if es_il:
            return [
                ("Crédito", kwargs.get("prestamo_id")),
                ("Tipo de crédito", tipo_credito),
                ("Fecha del abono", kwargs.get("fecha_pago")),
                ("Capital anterior", pesos(kwargs.get("capital_anterior"))),
                ("Abono realizado", pesos(kwargs.get("valor"))),
                ("Nuevo saldo capital", pesos(kwargs.get("saldo_capital"))),
                ("Interés acumulado", pesos(kwargs.get("interes_pendiente"))),
                ("Próxima fecha de interés", kwargs.get("fecha_proximo_interes")),
                ("Condición", "No se crean cuotas; solo se actualiza el capital vigente"),
            ]
        return [
            ("Crédito", kwargs.get("prestamo_id")),
            ("Tipo de crédito", tipo_credito),
            ("Fecha del abono", kwargs.get("fecha_pago")),
            ("Capital anterior", pesos(kwargs.get("capital_anterior"))),
            ("Abono a capital", pesos(kwargs.get("valor"))),
            ("Nuevo saldo capital", pesos(kwargs.get("saldo_capital"))),
            ("Nueva cuota estimada", pesos(kwargs.get("nueva_cuota"))),
            ("Cuotas pendientes", kwargs.get("cuotas_pendientes")),
        ]
    if tipo_correo == "CIERRE_CREDITO":
        return [
            ("Crédito", kwargs.get("prestamo_id")),
            ("Fecha de cierre", kwargs.get("fecha_pago")),
            ("Total aplicado", pesos(kwargs.get("valor"))),
            ("Estado", "Cuenta cerrada"),
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
    elif tipo_correo == "CIERRE_CREDITO":
        lineas.extend([
            "",
            "Gracias por completar el pago de su obligación. No registra cuotas pendientes para este crédito.",
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


def generar_contrato_pdf(prestamo_id, cliente, monto_credito, cuotas, valor_cuota, tipo_credito, fecha_emision=None, tasa_interes=None, fecha_proximo_interes=None):
    ruta_pdf = os.path.join(tempfile.gettempdir(), f"contrato_{prestamo_id}.pdf")
    fecha_emision = fecha_emision or hoy_local().isoformat()
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
    es_interes_libre = str(tipo_credito or "").strip().lower() in ("interés libre", "interes libre")
    if es_interes_libre:
        resumen_data = [
            [Paragraph("Crédito", style_label), Paragraph(f"<b>{prestamo_id}</b>", style_value), Paragraph("Fecha de emisión", style_label), Paragraph(f"<b>{fecha_emision}</b>", style_value)],
            [Paragraph("Cliente", style_label), Paragraph(f"<b>{cliente}</b>", style_value), Paragraph("Tipo de crédito", style_label), Paragraph(f"<b>{tipo_credito}</b>", style_value)],
            [Paragraph("Monto aprobado", style_label), Paragraph(f"<b>{pesos(monto_credito)}</b>", style_value), Paragraph("Tasa de interés", style_label), Paragraph(f"<b>{float(tasa_interes or 0) * 100:.2f}%</b>", style_value)],
            [Paragraph("Interés estimado 30 días", style_label), Paragraph(f"<b>{pesos(valor_cuota)}</b>", style_value), Paragraph("Próximo pago interés", style_label), Paragraph(f"<b>{fecha_proximo_interes or '-'}</b>", style_value)],
        ]
    else:
        resumen_data = [
            [Paragraph("Crédito", style_label), Paragraph(f"<b>{prestamo_id}</b>", style_value), Paragraph("Fecha de emisión", style_label), Paragraph(f"<b>{fecha_emision}</b>", style_value)],
            [Paragraph("Cliente", style_label), Paragraph(f"<b>{cliente}</b>", style_value), Paragraph("Tipo de crédito", style_label), Paragraph(f"<b>{tipo_credito}</b>", style_value)],
            [Paragraph("Monto aprobado", style_label), Paragraph(f"<b>{pesos(monto_credito)}</b>", style_value), Paragraph("Número de cuotas", style_label), Paragraph(f"<b>{cuotas}</b>", style_value)],
            [Paragraph("Valor de la cuota", style_label), Paragraph(f"<b>{pesos(valor_cuota)}</b>", style_value), Paragraph("Estado inicial", style_label), Paragraph("<b>Pendiente de aceptación</b>", style_value)],
        ]
    resumen = Table(resumen_data, colWidths=[doc.width * 0.18, doc.width * 0.32, doc.width * 0.18, doc.width * 0.32])
    resumen.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), fondo), ('BOX', (0, 0), (-1, -1), 1, gris_claro), ('INNERGRID', (0, 0), (-1, -1), 0.5, gris_claro), ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 9), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    story.append(resumen)
    story.append(Spacer(1, 16))
    story.append(Paragraph("<b>1. Objeto de la operación</b>", style_clause_title))
    story.append(Paragraph("Mediante el presente documento, CREDDT CRNTECH deja constancia de la aprobación inicial del crédito descrito en el resumen anterior y de las condiciones base de la operación financiera ofrecida al cliente.", style_clause))
    story.append(Paragraph("<b>2. Condiciones generales de pago</b>", style_clause_title))
    if es_interes_libre:
        story.append(Paragraph("El cliente se compromete a pagar el interés causado cada 30 días contados desde el desembolso. Este crédito no tiene cuotas programadas de capital; el capital permanecerá vigente hasta que el cliente realice abonos parciales o pago total al capital.", style_clause))
    else:
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

def construir_cuerpo_anulacion_contrato(nombre_cliente, prestamo_id, motivo):
    motivo_txt = (motivo or "No especificado").strip()
    return f"""Estimado(a) {nombre_cliente},

Reciba un cordial saludo de CREDDT CRNTECH.

Le informamos que el contrato asociado al crédito {prestamo_id} fue anulado en nuestro sistema debido a una validación administrativa.

Motivo registrado:
- {motivo_txt}

Este contrato queda sin efecto y el enlace de aceptación anterior ya no debe ser utilizado.

Ofrecemos disculpas por la novedad presentada. Si requiere una nueva validación o confirmación, nuestro equipo estará atento para brindarle apoyo.

Cordialmente,
CREDDT CRNTECH
Área Administrativa y Financiera"""

def construir_html_anulacion_contrato(nombre_cliente, prestamo_id, motivo):
    motivo_txt = (motivo or "No especificado").strip()
    return f"""
    <div style=\"margin:0;padding:24px;background:#f3f6fb;font-family:Arial,Helvetica,sans-serif;color:#0f172a;\">
        <div style=\"max-width:720px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;overflow:hidden;\">
            <div style=\"background:#0f172a;padding:28px 32px;\">
                <div style=\"font-size:24px;font-weight:800;color:#ffffff;letter-spacing:.2px;\">CREDDT CRNTECH</div>
                <div style=\"margin-top:6px;font-size:14px;color:#cbd5e1;\">Anulación de contrato de crédito</div>
            </div>
            <div style=\"padding:30px 32px;\">
                <p style=\"margin:0 0 16px 0;font-size:15px;line-height:1.75;\">Estimado(a) <strong>{nombre_cliente}</strong>,</p>
                <p style=\"margin:0 0 18px 0;font-size:15px;line-height:1.75;color:#334155;\">
                    Le informamos que el contrato asociado al crédito <strong>{prestamo_id}</strong> fue anulado en nuestro sistema debido a una validación administrativa.
                </p>
                <div style=\"background:#fff7ed;border:1px solid #fdba74;border-radius:14px;padding:18px 20px;margin:0 0 24px 0;\">
                    <div style=\"font-size:13px;font-weight:700;letter-spacing:.4px;color:#9a3412;margin-bottom:10px;text-transform:uppercase;\">Motivo registrado</div>
                    <div style=\"font-size:15px;line-height:1.7;color:#7c2d12;\">{motivo_txt}</div>
                </div>
                <p style=\"margin:0 0 18px 0;font-size:15px;line-height:1.75;color:#334155;\">
                    El enlace de aceptación anterior ya no debe ser utilizado. Ofrecemos disculpas por la novedad presentada.
                </p>
                <div style=\"border-top:1px solid #e5e7eb;padding-top:18px;margin-top:18px;\">
                    <p style=\"margin:0;font-size:14px;line-height:1.7;color:#334155;\">Cordialmente,<br><strong>CREDDT CRNTECH</strong><br>Área Administrativa y Financiera</p>
                </div>
            </div>
        </div>
    </div>
    """

def enviar_pdf_por_correo(destino, asunto, cuerpo, ruta_pdf, nombre_adj, html_override=None):
    with open(ruta_pdf, "rb") as f:
        return enviar_correo_async(destino=destino, asunto=asunto, cuerpo=cuerpo, attachment_bytes=f.read(), attachment_name=nombre_adj, html_override=html_override)


def registrar_auditoria_contrato(prestamo_id, accion, usuario=None, motivo=None, detalle=None):
    """Registra trazabilidad del flujo de contratos sin bloquear la operación principal."""
    try:
        with get_conn() as conn:
            conn.execute(text("""
                INSERT INTO auditoria_contratos (prestamo_id, accion, motivo, usuario, fecha, detalle)
                VALUES (:prestamo_id, :accion, :motivo, :usuario, :fecha, :detalle)
            """), {
                "prestamo_id": prestamo_id,
                "accion": accion,
                "motivo": motivo,
                "usuario": usuario or st.session_state.get("usuario") or "SISTEMA",
                "fecha": ahora_local().isoformat(timespec='seconds'),
                "detalle": detalle,
            })
            conn.commit()
    except Exception:
        pass


def enviar_contrato_credito(prestamo_row):
    """Genera y envía el contrato del crédito.

    Retorna (ok, error). Si el correo fue enviado, ok queda en True aunque
    falle la actualización del marcador en BD, para evitar mostrar un falso
    error de envío al usuario.
    """
    if not prestamo_row.get("correo"):
        return False, "Cliente sin correo registrado"

    if int(prestamo_row.get("contrato_cancelado", 0) or 0) == 1 or str(prestamo_row.get("estado") or "").strip().lower() == "anulado":
        return False, "El contrato está anulado y no puede reenviarse"

    if int(prestamo_row.get("contrato_aceptado", 0) or 0) == 1:
        return False, "El contrato ya fue aceptado y no corresponde reenviarlo"

    if not APP_BASE_URL:
        return False, "Falta configurar APP_BASE_URL para generar el enlace de aceptación"

    token = prestamo_row.get("contrato_token")
    try:
        if not token:
            token = uuid.uuid4().hex
            with get_conn() as conn:
                conn.execute(
                    text("UPDATE prestamos SET contrato_token = :token WHERE id = :id"),
                    {"token": token, "id": prestamo_row["id"]}
                )
                conn.commit()

        enlace = f"{APP_BASE_URL}?aceptar={token}"
        ruta_pdf = generar_contrato_pdf(
            prestamo_row["id"],
            prestamo_row["cliente"],
            prestamo_row["monto_original"],
            prestamo_row["cuotas"],
            prestamo_row["valor_cuota"],
            prestamo_row.get("tipo", "Normal"),
            tasa_interes=prestamo_row.get("tasa_mensual", 0),
            fecha_proximo_interes=prestamo_row.get("fecha_proximo_interes")
        )

        try:
            cuerpo = construir_cuerpo_correo(
                "CONTRATO",
                prestamo_row["cliente"],
                prestamo_id=prestamo_row["id"],
                monto=prestamo_row["monto_original"],
                cuotas=prestamo_row["cuotas"],
                valor_cuota=prestamo_row["valor_cuota"],
                tipo_credito=prestamo_row.get("tipo"),
                tipo_credito_codigo=prestamo_row.get("tipo_credito"),
                frecuencia=prestamo_row.get("frecuencia", "Mensual"),
                saldo_capital=prestamo_row.get("saldo_capital") or prestamo_row.get("monto_original"),
                tasa_interes=prestamo_row.get("tasa_mensual"),
                fecha_proximo_interes=prestamo_row.get("fecha_proximo_interes"),
                link_aceptacion=enlace
            )
            html_correo = construir_html_correo(
                "CONTRATO",
                prestamo_row["cliente"],
                prestamo_id=prestamo_row["id"],
                monto=prestamo_row["monto_original"],
                cuotas=prestamo_row["cuotas"],
                valor_cuota=prestamo_row["valor_cuota"],
                tipo_credito=prestamo_row.get("tipo"),
                tipo_credito_codigo=prestamo_row.get("tipo_credito"),
                frecuencia=prestamo_row.get("frecuencia", "Mensual"),
                saldo_capital=prestamo_row.get("saldo_capital") or prestamo_row.get("monto_original"),
                tasa_interes=prestamo_row.get("tasa_mensual"),
                fecha_proximo_interes=prestamo_row.get("fecha_proximo_interes"),
                link_aceptacion=enlace
            )

            with open(ruta_pdf, "rb") as f:
                ok_mail, err_mail = enviar_correo_async(
                    prestamo_row["correo"],
                    "CREDDT CRNTECH | Contrato de crédito para aceptación",
                    cuerpo,
                    attachment_bytes=f.read(),
                    attachment_name=f"contrato_{prestamo_row['id']}.pdf",
                    html_override=html_correo
                )

            if not ok_mail:
                return False, err_mail

            try:
                with get_conn() as conn:
                    conn.execute(text("""
                        UPDATE prestamos
                        SET contrato_enviado = 1,
                            fecha_envio_contrato = :fecha
                        WHERE id = :id
                    """), {"fecha": ahora_local().isoformat(timespec='seconds'), "id": prestamo_row["id"]})
                    conn.commit()
                clear_app_caches()
                registrar_auditoria_contrato(prestamo_row["id"], "ENVIO_CONTRATO", detalle=f"Contrato enviado a {prestamo_row.get('correo')}")
            except Exception as e_bd:
                registrar_auditoria_contrato(prestamo_row["id"], "ENVIO_CONTRATO", detalle=f"Correo enviado a {prestamo_row.get('correo')}, pero falló el update de BD: {e_bd}")
                return True, f"Correo enviado, pero no se pudo marcar el contrato como enviado en BD: {e_bd}"

            return True, None
        finally:
            if ruta_pdf and os.path.exists(ruta_pdf):
                try:
                    os.remove(ruta_pdf)
                except Exception:
                    pass

    except Exception as e:
        return False, f"Error enviando contrato: {e}"


def enviar_correo_desembolso_credito(prestamo_row):
    if not prestamo_row.get("correo"):
        return False, "Cliente sin correo registrado"
    es_il = es_credito_interes_libre_row(prestamo_row)
    saldo_pendiente = (prestamo_row.get("saldo_capital") or prestamo_row.get("monto_original")) if es_il else (prestamo_row.get("monto_total_credito") or prestamo_row.get("saldo") or prestamo_row.get("monto_original"))
    kwargs = dict(
        prestamo_id=prestamo_row["id"],
        tipo_credito=prestamo_row.get("tipo"),
        tipo_credito_codigo=prestamo_row.get("tipo_credito"),
        monto=prestamo_row["monto_original"],
        saldo_capital=prestamo_row.get("saldo_capital") or prestamo_row.get("monto_original"),
        tasa_interes=prestamo_row.get("tasa_mensual"),
        frecuencia=prestamo_row.get("frecuencia", "Mensual"),
        cuotas=prestamo_row["cuotas"],
        valor_cuota=prestamo_row["valor_cuota"],
        fecha_proximo_interes=prestamo_row.get("fecha_proximo_interes"),
        saldo_pendiente=saldo_pendiente,
        estado="Activo",
    )
    cuerpo = construir_cuerpo_correo("DESEMBOLSO", prestamo_row["cliente"], **kwargs)
    html_correo = construir_html_correo("DESEMBOLSO", prestamo_row["cliente"], **kwargs)
    ok_mail, err_mail = enviar_correo_async(prestamo_row["correo"], f"CREDDT CRNTECH | Confirmación de desembolso del crédito {prestamo_row['id']}", cuerpo, html_override=html_correo)
    if ok_mail:
        with get_conn() as conn:
            conn.execute(text("""
                UPDATE prestamos
                SET desembolso_notificado = 1,
                    fecha_desembolso = COALESCE(fecha_desembolso, :fecha)
                WHERE id = :id
            """), {"fecha": ahora_local().isoformat(timespec='seconds'), "id": prestamo_row["id"]})
            conn.commit()
        clear_app_caches()
    return ok_mail, err_mail

def guardar_cliente_db(data):
    with get_conn() as conn:
        conn.execute(text("""
            INSERT INTO clientes (cedula, nombres, apellidos, ciudad, telefono, correo, direccion, empresa, fecha_nacimiento, cargo)
            VALUES (:cedula, :nombres, :apellidos, :ciudad, :telefono, :correo, :direccion, :empresa, :fecha_nacimiento, :cargo)
        """), data)
        conn.commit()
    clear_app_caches()
def actualizar_cliente_db(cedula, data):
    with get_conn() as conn:
        conn.execute(text("""
            UPDATE clientes
            SET nombres=:nombres, apellidos=:apellidos, ciudad=:ciudad, telefono=:telefono, correo=:correo,
                direccion=:direccion, empresa=:empresa, fecha_nacimiento=:fecha_nacimiento, cargo=:cargo
            WHERE cedula=:cedula
        """), {**data, "cedula": cedula})
        conn.commit()
    clear_app_caches()
def eliminar_cliente_db(cedula):
    with get_conn() as conn:
        existe = conn.execute(text("SELECT COUNT(*) FROM prestamos WHERE cliente_cedula = :cedula"), {"cedula": cedula}).scalar()
        if int(existe or 0) > 0:
            return False, "No se puede eliminar el cliente porque tiene créditos asociados"
        conn.execute(text("DELETE FROM clientes WHERE cedula = :cedula"), {"cedula": cedula})
        conn.commit()
    clear_app_caches()
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
    fecha_inicio = fecha_inicio or hoy_local()
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
        clear_app_caches()
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


def crear_credito_interes_libre_db(cliente_cedula, monto, tasa_interes_pct, fecha_inicio=None):
    fecha_inicio = fecha_inicio or hoy_local()
    monto = float(monto or 0)
    tasa_mensual = max(float(tasa_interes_pct or 0), 0) / 100
    if monto <= 0 or tasa_mensual <= 0:
        return False, "Monto o tasa inválidos", None
    fecha_proximo = fecha_inicio + timedelta(days=30)
    interes_30_dias = round(monto * tasa_mensual, 2)
    with get_conn() as conn:
        cliente = conn.execute(text("SELECT cedula, nombres, apellidos, correo FROM clientes WHERE cedula = :cedula"), {"cedula": cliente_cedula}).mappings().first()
        if not cliente:
            return False, "El cliente no está registrado", None
        prestamo_id = obtener_nuevo_id_prestamo("IL")
        contrato_token = uuid.uuid4().hex
        conn.execute(text("""
            INSERT INTO prestamos (
                id, cliente_cedula, monto_original, cuotas, frecuencia, valor_cuota, estado, tipo, tipo_credito,
                saldo_capital, tasa_mensual, interes_acumulado, fecha_ultimo_corte_interes, fecha_proximo_interes,
                contrato_aceptado, contrato_token, fecha_inicio
            )
            VALUES (
                :id, :cliente_cedula, :monto_original, 0, 'Mensual', :valor_cuota, 'Pendiente', 'Interés Libre', 'interes_libre',
                :saldo_capital, :tasa_mensual, 0, :fecha_inicio, :fecha_proximo_interes,
                0, :contrato_token, :fecha_inicio
            )
        """), {
            "id": prestamo_id,
            "cliente_cedula": cliente_cedula,
            "monto_original": monto,
            "valor_cuota": interes_30_dias,
            "saldo_capital": monto,
            "tasa_mensual": tasa_mensual,
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_proximo_interes": fecha_proximo.isoformat(),
            "contrato_token": contrato_token,
        })
        conn.commit()
        clear_app_caches()
        prestamo_row = {
            "id": prestamo_id,
            "cliente": f"{cliente['nombres']} {cliente['apellidos']}",
            "correo": cliente["correo"],
            "monto_original": monto,
            "cuotas": 0,
            "frecuencia": "Mensual",
            "valor_cuota": interes_30_dias,
            "tipo": "Interés Libre",
            "tipo_credito": "interes_libre",
            "tasa_mensual": tasa_mensual,
            "fecha_proximo_interes": fecha_proximo.isoformat(),
            "contrato_token": contrato_token,
        }
    ok_mail, err_mail = enviar_contrato_credito(prestamo_row)
    return True, None if ok_mail else err_mail, prestamo_row

def _fecha_iso_a_date(valor, default=None):
    if not valor:
        return default or hoy_local()
    try:
        return date.fromisoformat(str(valor)[:10])
    except Exception:
        return default or hoy_local()

def calcular_interes_libre_a_fecha(prestamo_row, fecha_pago):
    saldo_capital = normalizar_decimal(prestamo_row["saldo_capital"])
    tasa_mensual = Decimal(str(prestamo_row["tasa_mensual"] or 0))
    acumulado = normalizar_decimal(prestamo_row.get("interes_acumulado", 0))
    fecha_base = _fecha_iso_a_date(prestamo_row.get("fecha_ultimo_corte_interes") or prestamo_row.get("fecha_inicio"), fecha_pago)
    dias = max((fecha_pago - fecha_base).days, 0)
    interes_nuevo = (saldo_capital * tasa_mensual * Decimal(dias) / Decimal(30)).quantize(Decimal("0.01"))
    return (acumulado + interes_nuevo).quantize(Decimal("0.01")), dias

def registrar_pago_interes_libre(prestamo_id, fecha_pago, valor_pago, modo_pago="interes"):
    valor_pago = normalizar_decimal(valor_pago)
    modo_pago = str(modo_pago or "interes").strip().lower()
    if valor_pago <= 0:
        return {"ok": False, "error": "El valor pagado debe ser mayor a cero"}
    if modo_pago not in ("interes", "finalizar"):
        return {"ok": False, "error": "Modo de pago de interés libre inválido"}

    with get_conn() as conn:
        prestamo = conn.execute(text("""
            SELECT p.*, c.nombres || ' ' || c.apellidos AS cliente, c.correo
            FROM prestamos p
            JOIN clientes c ON c.cedula = p.cliente_cedula
            WHERE p.id = :id
              AND (
                    LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) = 'interes_libre'
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo_credito, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
                    OR LOWER(TRANSLATE(TRIM(COALESCE(p.tipo, '')), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')) IN ('interes libre', 'solo interes libre')
              )
        """), {"id": prestamo_id}).mappings().first()
        if not prestamo:
            return {"ok": False, "error": "No se encontró el crédito de interés libre"}
        if int(prestamo.get("contrato_cancelado", 0) or 0) == 1 or str(prestamo.get("estado") or "").strip().lower() in ("cancelado", "anulado"):
            return {"ok": False, "error": "Este crédito no está activo para recibir pagos"}

        interes_pendiente, dias = calcular_interes_libre_a_fecha(prestamo, fecha_pago)
        saldo_capital = normalizar_decimal(prestamo["saldo_capital"])

        tolerancia = Decimal("1.00")  # tolerancia de redondeo en pesos para absorber diferencias float/Decimal

        if modo_pago == "interes":
            if interes_pendiente <= 0:
                return {"ok": False, "error": "Este crédito no tiene interés pendiente para la fecha seleccionada"}
            if abs(valor_pago - interes_pendiente) > tolerancia:
                return {"ok": False, "error": f"Para pagar solo interés el valor debe ser aproximadamente {pesos(interes_pendiente)} (interés calculado a la fecha de pago). El capital no se abona desde esta opción."}
            # Se usa el interés calculado por el sistema (fuente de verdad) y no el valor tecleado,
            # para evitar que pequeñas diferencias de redondeo dejen saldos de centavos sueltos.
            valor_pago = interes_pendiente
            interes_pagado = interes_pendiente
            capital_pagado = Decimal("0.00")
            nuevo_interes = Decimal("0.00")
            nuevo_capital = saldo_capital
            nuevo_estado = "Activo"
            fecha_proximo = fecha_pago + timedelta(days=30)
            tipo_movimiento = "INTERES_LIBRE"
            detalle = f"Pago cuota interés libre por {interes_pagado}"
            fecha_cierre_manual = None
        else:
            total_esperado = (interes_pendiente + saldo_capital).quantize(Decimal("0.01"))
            if abs(valor_pago - total_esperado) > tolerancia:
                return {"ok": False, "error": f"Para finalizar la deuda el valor debe ser aproximadamente {pesos(total_esperado)}: interés {pesos(interes_pendiente)} + capital {pesos(saldo_capital)}."}
            valor_pago = total_esperado
            interes_pagado = interes_pendiente
            capital_pagado = saldo_capital
            nuevo_interes = Decimal("0.00")
            nuevo_capital = Decimal("0.00")
            nuevo_estado = "Cancelado"
            fecha_proximo = None
            tipo_movimiento = "CIERRE_INTERES_LIBRE"
            detalle = f"Pago final interés libre: interés {interes_pagado}, capital {capital_pagado}"
            fecha_cierre_manual = ahora_local().isoformat(timespec='seconds')

        result = conn.execute(text("""
            INSERT INTO pagos (
                prestamo_id, fecha_pago, valor, estado, tipo_movimiento, detalle,
                interes_pagado, capital_pagado, saldo_capital_anterior, saldo_capital_nuevo, cuota_numero
            )
            VALUES (
                :id, :fecha, :valor, 'Pagado', :tipo_movimiento, :detalle,
                :interes_pagado, :capital_pagado, :saldo_capital_anterior, :saldo_capital_nuevo, NULL
            )
            RETURNING id_pago
        """), {
            "id": prestamo_id,
            "fecha": fecha_pago.isoformat(),
            "valor": valor_pago,
            "tipo_movimiento": tipo_movimiento,
            "detalle": detalle,
            "interes_pagado": interes_pagado,
            "capital_pagado": capital_pagado,
            "saldo_capital_anterior": saldo_capital,
            "saldo_capital_nuevo": nuevo_capital,
        })
        id_pago = result.fetchone()[0]
        conn.execute(text("""
            UPDATE prestamos
            SET saldo_capital = :saldo_capital,
                interes_acumulado = :interes_acumulado,
                fecha_ultimo_corte_interes = :fecha_corte,
                fecha_proximo_interes = :fecha_proximo,
                valor_cuota = ROUND(:saldo_capital * tasa_mensual, 2),
                estado = :estado,
                fecha_cierre_manual = COALESCE(:fecha_cierre_manual, fecha_cierre_manual)
            WHERE id = :id
        """), {
            "id": prestamo_id,
            "saldo_capital": nuevo_capital,
            "interes_acumulado": nuevo_interes,
            "fecha_corte": fecha_pago.isoformat(),
            "fecha_proximo": fecha_proximo.isoformat() if fecha_proximo else None,
            "estado": nuevo_estado,
            "fecha_cierre_manual": fecha_cierre_manual,
        })
        conn.commit()
        clear_app_caches()

    pdf = None
    correo_ok = False
    correo_error = None
    try:
        titulo_pdf = "RECIBO DE PAGO INTERÉS LIBRE" if modo_pago == "interes" else "RECIBO DE CIERRE INTERÉS LIBRE"
        pdf = generar_recibo_pdf(prestamo_id, prestamo["cliente"], prestamo["monto_original"], fecha_pago.isoformat(), valor_pago, titulo=titulo_pdf, subtitulo="VALOR PAGADO")
        kwargs = dict(
            prestamo_id=prestamo_id,
            tipo_credito="Interés libre",
            tipo_credito_codigo="interes_libre",
            fecha_pago=fecha_pago.isoformat(),
            valor=valor_pago,
            interes_pagado=interes_pagado,
            capital_pagado=capital_pagado,
            saldo_capital=nuevo_capital,
            interes_pendiente=nuevo_interes,
            fecha_proximo_interes=fecha_proximo.isoformat() if fecha_proximo else "Crédito finalizado",
            tasa_interes=prestamo.get("tasa_mensual"),
            estado=nuevo_estado,
        )
        cuerpo = construir_cuerpo_correo("RECIBO_CUOTA", prestamo["cliente"], **kwargs)
        html_correo = construir_html_correo("RECIBO_CUOTA", prestamo["cliente"], **kwargs)
        correo_cliente = (prestamo.get("correo") or "").strip()
        if correo_cliente:
            correo_ok, correo_error = enviar_pdf_por_correo(correo_cliente, f"CREDDT CRNTECH | Confirmación de pago del crédito {prestamo_id}", cuerpo, pdf, f"recibo_{prestamo_id}.pdf", html_override=html_correo)
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
        "id_pago": id_pago,
        "valor": valor_pago,
        "interes_pagado": interes_pagado,
        "capital_pagado": capital_pagado,
        "saldo_capital": nuevo_capital,
        "interes_pendiente": nuevo_interes,
        "dias": dias,
        "fecha_proximo_interes": fecha_proximo.isoformat() if fecha_proximo else "Finalizado",
        "modo_pago": modo_pago,
        "correo": correo_ok,
        "tiene_correo": bool(prestamo.get("correo")),
        "correo_error": correo_error,
        "finalizado": modo_pago == "finalizar",
    }

def cerrar_credito_interes_libre(prestamo_id):
    with get_conn() as conn:
        prestamo = conn.execute(text("""
            SELECT id, COALESCE(saldo_capital, monto_original) AS saldo_capital, COALESCE(interes_acumulado, 0) AS interes_acumulado
            FROM prestamos
            WHERE id = :id AND LOWER(REPLACE(REPLACE(TRIM(COALESCE(tipo_credito, '')), 'é', 'e'), 'É', 'e')) = 'interes_libre'
        """), {"id": prestamo_id}).mappings().first()
        if not prestamo:
            return False, "No se encontró el crédito de interés libre"
        if normalizar_decimal(prestamo["saldo_capital"]) > 0 or normalizar_decimal(prestamo["interes_acumulado"]) > 0:
            return False, "Para cerrar manualmente, capital e intereses deben estar en cero"
        conn.execute(text("""
            UPDATE prestamos
            SET estado = 'Cancelado',
                fecha_cierre_manual = :fecha
            WHERE id = :id
        """), {"id": prestamo_id, "fecha": ahora_local().isoformat(timespec='seconds')})
        conn.commit()
        clear_app_caches()
    return True, "Crédito interés libre cerrado manualmente"

def cancelar_contrato_prestamo(prestamo_id, motivo, usuario=None):
    motivo = (motivo or "").strip()
    if not motivo:
        return False, "Debes indicar el motivo de la anulación"

    with get_conn() as conn:
        prestamo = conn.execute(text("""
            SELECT p.id, p.estado, p.contrato_aceptado, COALESCE(p.contrato_cancelado, 0) AS contrato_cancelado,
                   p.cliente_cedula, c.nombres || ' ' || c.apellidos AS cliente, c.correo
            FROM prestamos p
            JOIN clientes c ON c.cedula = p.cliente_cedula
            WHERE p.id = :id
        """), {"id": prestamo_id}).mappings().first()

        if not prestamo:
            return False, "No se encontró el crédito seleccionado"

        if int(prestamo["contrato_aceptado"] or 0) == 1:
            return False, "No se puede anular porque el contrato ya fue aceptado"

        if int(prestamo["contrato_cancelado"] or 0) == 1 or str(prestamo["estado"] or "").strip().lower() == "anulado":
            return False, "Este contrato ya fue anulado previamente"

        conn.execute(text("""
            UPDATE prestamos
            SET estado = 'Anulado',
                contrato_cancelado = 1,
                fecha_cancelacion_contrato = :fecha,
                motivo_cancelacion_contrato = :motivo,
                cancelado_por = :usuario,
                contrato_token = NULL
            WHERE id = :id
        """), {
            "fecha": ahora_local().isoformat(timespec='seconds'),
            "motivo": motivo,
            "usuario": usuario or st.session_state.get("usuario") or "SISTEMA",
            "id": prestamo_id
        })
        conn.execute(text("""
            UPDATE cuotas
            SET estado = 'Anulada'
            WHERE prestamo_id = :id
              AND estado IN ('Pendiente', 'Parcial')
        """), {"id": prestamo_id})
        conn.commit()

    clear_app_caches()
    registrar_auditoria_contrato(prestamo_id, "ANULACION_CONTRATO", usuario=usuario, motivo=motivo, detalle="Contrato anulado manualmente desde la app")

    correo_ok = False
    correo_error = None
    if (prestamo.get("correo") or "").strip():
        cuerpo = construir_cuerpo_anulacion_contrato(prestamo["cliente"], prestamo_id, motivo)
        html = construir_html_anulacion_contrato(prestamo["cliente"], prestamo_id, motivo)
        correo_ok, correo_error = enviar_correo_async(
            prestamo["correo"],
            f"CREDDT CRNTECH | Actualización del contrato del crédito {prestamo_id}",
            cuerpo,
            html_override=html
        )
    else:
        correo_error = "Cliente sin correo registrado"

    return True, {
        "prestamo_id": prestamo_id,
        "correo": correo_ok,
        "correo_error": correo_error,
        "cliente": prestamo["cliente"],
    }

def aceptar_contrato_por_token(token):
    with get_conn() as conn:
        prestamo = conn.execute(text("""
            SELECT p.id, p.cliente_cedula, p.monto_original, p.cuotas, p.frecuencia, p.valor_cuota, p.tipo, p.estado,
                   p.tipo_credito, p.tasa_mensual, p.fecha_proximo_interes,
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
                fecha_aceptacion = :fecha,
                fecha_desembolso = COALESCE(fecha_desembolso, :fecha)
            WHERE id = :id
        """), {"fecha": ahora_local().isoformat(timespec='seconds'), "id": prestamo["id"]})
        if es_credito_interes_libre_valor(prestamo.get("tipo_credito"), prestamo.get("tipo")):
            fecha_base = hoy_local()
            conn.execute(text("""
                UPDATE prestamos
                SET fecha_ultimo_corte_interes = :fecha_base,
                    fecha_proximo_interes = :fecha_proximo,
                    valor_cuota = ROUND(COALESCE(saldo_capital, monto_original) * COALESCE(tasa_mensual, 0), 2)
                WHERE id = :id
            """), {"fecha_base": fecha_base.isoformat(), "fecha_proximo": (fecha_base + timedelta(days=30)).isoformat(), "id": prestamo["id"]})
        conn.commit()
    clear_app_caches()
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
              AND cu.fecha_vencimiento::date BETWEEN (CAST(:hoy AS date) - INTERVAL '5 day') AND (CAST(:hoy AS date) + INTERVAL '3 day')
              AND (LOWER(TRIM(COALESCE(p.estado, ''))) = 'activo' OR COALESCE(p.contrato_aceptado, 0) = 1)
              AND COALESCE(p.contrato_cancelado, 0) = 0
              AND NOT ((LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) = 'interes_libre' OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre') OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre')) OR LOWER(TRIM(COALESCE(p.tipo, ''))) IN ('interes libre', 'interés libre'))
        """), {"hoy": hoy_local().isoformat()}).mappings().all()
        for r in rows:
            dias = (r['fecha_vencimiento'] - hoy_local()).days
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
                conn.execute(text("INSERT INTO reminders_sent (id_cuota, tipo_recordatorio, fecha_envio) VALUES (:id_cuota, :tipo, :fecha_envio)"), {"id_cuota": r['id_cuota'], "tipo": tipo_r, "fecha_envio": ahora_local().isoformat(timespec='seconds')})
                enviados += 1

        # --- Créditos de interés libre ---
        # Estos créditos no generan filas en "cuotas"; su próximo vencimiento vive en
        # prestamos.fecha_proximo_interes. Antes quedaban excluidos de los recordatorios
        # por completo; aquí se agrega el mismo esquema D-3/D-1/D0/D+1/D+5 para ellos.
        rows_il = conn.execute(text("""
            SELECT p.id AS prestamo_id, p.fecha_proximo_interes::date AS fecha_proximo_interes,
                   COALESCE(p.saldo_capital, p.monto_original) AS saldo_capital,
                   COALESCE(p.tasa_mensual, 0) AS tasa_mensual,
                   COALESCE(p.interes_acumulado, 0) AS interes_acumulado,
                   p.fecha_ultimo_corte_interes,
                   c.nombres || ' ' || c.apellidos AS cliente, c.correo
            FROM prestamos p
            JOIN clientes c ON c.cedula = p.cliente_cedula
            WHERE p.fecha_proximo_interes IS NOT NULL
              AND c.correo IS NOT NULL
              AND p.fecha_proximo_interes::date BETWEEN (CAST(:hoy AS date) - INTERVAL '5 day') AND (CAST(:hoy AS date) + INTERVAL '3 day')
              AND (LOWER(TRIM(COALESCE(p.estado, ''))) = 'activo' OR COALESCE(p.contrato_aceptado, 0) = 1)
              AND COALESCE(p.contrato_cancelado, 0) = 0
              AND (LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) = 'interes_libre' OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre') OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre') OR LOWER(TRIM(COALESCE(p.tipo, ''))) IN ('interes libre', 'interés libre'))
        """), {"hoy": hoy_local().isoformat()}).mappings().all()
        for r in rows_il:
            dias = (r['fecha_proximo_interes'] - hoy_local()).days
            if dias not in tipos_permitidos:
                continue
            tipo_r = tipos_permitidos[dias]
            # Se combina el tipo de recordatorio con la fecha del ciclo para que, al pagar
            # y generarse un nuevo fecha_proximo_interes, sí se puedan volver a enviar
            # recordatorios en el siguiente ciclo (y no solo una vez por crédito).
            tipo_recordatorio_il = f"IL_{tipo_r}_{r['fecha_proximo_interes'].isoformat()}"
            id_cuota_sintetico = -int(r['prestamo_id'])
            ya = conn.execute(text("SELECT COUNT(*) FROM reminders_sent WHERE id_cuota = :id_cuota AND tipo_recordatorio = :tipo"), {"id_cuota": id_cuota_sintetico, "tipo": tipo_recordatorio_il}).scalar()
            if int(ya or 0) > 0:
                continue
            interes_estimado, _dias_calc = calcular_interes_libre_a_fecha(dict(r), r['fecha_proximo_interes'])
            cuerpo = construir_cuerpo_correo('RECORDATORIO', r['cliente'], prestamo_id=r['prestamo_id'], cuota_nro='Interés libre', fecha_vencimiento=r['fecha_proximo_interes'], valor=interes_estimado)
            html_correo = construir_html_correo('RECORDATORIO', r['cliente'], prestamo_id=r['prestamo_id'], cuota_nro='Interés libre', fecha_vencimiento=r['fecha_proximo_interes'], valor=interes_estimado)
            ok, _ = enviar_correo_async(r['correo'], f"CREDDT CRNTECH | Recordatorio de pago de interés del crédito {r['prestamo_id']}", cuerpo, html_override=html_correo)
            if ok:
                conn.execute(text("INSERT INTO reminders_sent (id_cuota, tipo_recordatorio, fecha_envio) VALUES (:id_cuota, :tipo, :fecha_envio)"), {"id_cuota": id_cuota_sintetico, "tipo": tipo_recordatorio_il, "fecha_envio": ahora_local().isoformat(timespec='seconds')})
                enviados += 1

        conn.commit()
    clear_app_caches()
    return enviados

def render_aceptacion_contrato(token):
    st.markdown("<h2 style='text-align:center;'>CREDDT | CRNTECH</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#666;'>Aceptación de contrato de crédito</p>", unsafe_allow_html=True)
    with get_conn() as conn:
        prestamo = conn.execute(text("""
            SELECT p.id, p.monto_original, p.cuotas, p.frecuencia, p.valor_cuota, p.tipo, p.estado, p.contrato_aceptado,
                   COALESCE(p.contrato_cancelado, 0) AS contrato_cancelado, p.fecha_cancelacion_contrato, p.motivo_cancelacion_contrato,
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
    if int(prestamo.get('contrato_cancelado', 0) or 0) == 1 or str(prestamo.get('estado') or '').strip().lower() == 'anulado':
        st.error("❌ Este contrato fue anulado y el enlace ya no es válido.")
        motivo = prestamo.get('motivo_cancelacion_contrato') or '-'
        fecha_c = prestamo.get('fecha_cancelacion_contrato') or '-'
        st.caption(f"Fecha de anulación: {fecha_c} | Motivo: {motivo}")
        return
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
    estado_credito = str(prestamo_row.get("estado") or "").strip().lower()
    if estado_credito != "activo" or int(prestamo_row.get("contrato_cancelado", 0) or 0) == 1:
        return False, "El crédito está anulado/cancelado o no está activo; no se envía recordatorio"
    if es_credito_interes_libre_row(prestamo_row):
        fecha_prox = prestamo_row.get("fecha_proximo_interes")
        if not fecha_prox:
            return False, "El crédito de interés libre no tiene una fecha de próximo interés registrada"
        fecha_prox_date = _fecha_iso_a_date(fecha_prox)
        interes_estimado, _ = calcular_interes_libre_a_fecha(prestamo_row, fecha_prox_date)
        cuerpo = construir_cuerpo_correo(
            "RECORDATORIO",
            prestamo_row["cliente"],
            prestamo_id=prestamo_row["id"],
            cuota_nro="Interés libre",
            fecha_vencimiento=fecha_prox,
            valor=interes_estimado
        )
        return enviar_correo_async(
            prestamo_row["correo"],
            f"Recordatorio de pago de interés del crédito {prestamo_row['id']}",
            cuerpo
        )
    with get_conn() as conn:
        proxima = conn.execute(text("""
            SELECT cu.id_cuota, cu.nro_cuota, cu.valor_cuota, cu.fecha_vencimiento, cu.estado
            FROM cuotas cu
            JOIN prestamos p ON p.id = cu.prestamo_id
            WHERE cu.prestamo_id = :id
              AND cu.estado <> 'Pagada'
              AND (LOWER(TRIM(COALESCE(p.estado, ''))) = 'activo' OR COALESCE(p.contrato_aceptado, 0) = 1)
              AND COALESCE(p.contrato_cancelado, 0) = 0
              AND NOT ((LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) = 'interes_libre' OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo_credito, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre') OR LOWER(REPLACE(REPLACE(TRIM(COALESCE(p.tipo, '')), 'é', 'e'), 'É', 'e')) IN ('interes libre', 'solo interes libre')) OR LOWER(TRIM(COALESCE(p.tipo, ''))) IN ('interes libre', 'interés libre'))
            ORDER BY cu.nro_cuota ASC
            LIMIT 1
        """), {"id": prestamo_row["id"]}).fetchone()
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

def obtener_cuotas_pendientes(conn, prestamo_id):
    return conn.execute(text("""
        SELECT id_cuota, nro_cuota, valor_cuota, fecha_vencimiento, estado
        FROM cuotas
        WHERE prestamo_id = :id
          AND estado <> 'Pagada'
        ORDER BY nro_cuota ASC
    """), {"id": prestamo_id}).fetchall()

def enviar_correo_cierre_credito(prestamo_id, nombre_cliente, correo_cliente, fecha_pago, valor_aplicado):
    if not correo_cliente:
        return False, "Cliente sin correo registrado"
    cuerpo = construir_cuerpo_correo(
        "CIERRE_CREDITO",
        nombre_cliente,
        prestamo_id=prestamo_id,
        fecha_pago=fecha_pago.isoformat(),
        valor=valor_aplicado
    )
    html_correo = construir_html_correo(
        "CIERRE_CREDITO",
        nombre_cliente,
        prestamo_id=prestamo_id,
        fecha_pago=fecha_pago.isoformat(),
        valor=valor_aplicado
    )
    return enviar_correo_async(
        correo_cliente,
        f"CREDDT CRNTECH | Crédito {prestamo_id} finalizado",
        cuerpo,
        html_override=html_correo
    )

def registrar_pago_cuota(prestamo_id, fecha_pago):
    return registrar_pago_cuotas(prestamo_id, fecha_pago, cantidad_cuotas=1)

def registrar_pago_cuotas(prestamo_id, fecha_pago, cantidad_cuotas=None, valor_pago_total=None):
    if cantidad_cuotas is None and valor_pago_total is None:
        return {"ok": False, "error": "Debes indicar cuántas cuotas o qué valor aplicar"}
    if cantidad_cuotas is not None:
        cantidad_cuotas = int(cantidad_cuotas or 0)
        if cantidad_cuotas <= 0:
            return {"ok": False, "error": "La cantidad de cuotas debe ser mayor a cero"}
    valor_pago_total = normalizar_decimal(valor_pago_total) if valor_pago_total is not None else None
    if valor_pago_total is not None and valor_pago_total <= 0:
        return {"ok": False, "error": "El valor pagado debe ser mayor a cero"}

    with get_conn() as conn:
        prestamo_db = conn.execute(text("""
            SELECT id, cliente_cedula, monto_original, COALESCE(saldo_capital, monto_original) AS saldo_capital,
                   COALESCE(tasa_mensual, 0) AS tasa_mensual, valor_cuota
            FROM prestamos
            WHERE id = :id
        """), {"id": prestamo_id}).mappings().first()
        if not prestamo_db:
            return {"ok": False, "error": "No se pudo obtener el préstamo"}
        cuotas_pendientes = obtener_cuotas_pendientes(conn, prestamo_id)
        if not cuotas_pendientes:
            return {"ok": False, "error": "Todas las cuotas ya están pagadas"}
        aplicaciones = []
        restante = valor_pago_total
        if cantidad_cuotas is not None:
            cuotas_a_aplicar = cuotas_pendientes[:cantidad_cuotas]
            if len(cuotas_a_aplicar) < cantidad_cuotas:
                return {"ok": False, "error": "No hay suficientes cuotas pendientes para aplicar esa cantidad"}
            aplicaciones = [(cuota, normalizar_decimal(cuota[2]), True) for cuota in cuotas_a_aplicar]
            valor_pago = sum((valor for _, valor, _ in aplicaciones), Decimal("0.00"))
        else:
            for cuota in cuotas_pendientes:
                valor_cuota_actual = normalizar_decimal(cuota[2])
                if restante >= valor_cuota_actual:
                    aplicaciones.append((cuota, valor_cuota_actual, True))
                    restante -= valor_cuota_actual
                elif restante > 0:
                    aplicaciones.append((cuota, restante, False))
                    restante = Decimal("0.00")
                    break
                else:
                    break
            if not aplicaciones:
                return {"ok": False, "error": "El valor no alcanza para aplicar a una cuota"}
            if restante and restante > 0:
                return {"ok": False, "error": "El valor pagado supera el saldo de cuotas pendientes"}
            valor_pago = valor_pago_total
        saldo_capital_actual = normalizar_decimal(prestamo_db["saldo_capital"])
        tasa_mensual = Decimal(str(prestamo_db["tasa_mensual"] or 0))
        saldo_iterado = saldo_capital_actual
        interes_total = Decimal("0.00")
        capital_total = Decimal("0.00")
        for _, valor_aplicado, _ in aplicaciones:
            interes_periodo = (saldo_iterado * tasa_mensual).quantize(Decimal("0.01")) if tasa_mensual > 0 else Decimal("0.00")
            interes_aplicado = min(interes_periodo, valor_aplicado)
            capital_aplicado = valor_aplicado - interes_aplicado
            if capital_aplicado < 0:
                capital_aplicado = Decimal("0.00")
            saldo_iterado -= capital_aplicado
            if saldo_iterado < 0:
                saldo_iterado = Decimal("0.00")
            interes_total += interes_aplicado
            capital_total += capital_aplicado
        nuevo_saldo_capital = saldo_iterado
        primera_cuota = aplicaciones[0][0]
        ultima_cuota = aplicaciones[-1][0]
        cuotas_pagadas = [a[0][1] for a in aplicaciones if a[2]]
        detalle_cuotas = (
            f"Pago cuotas #{cuotas_pagadas[0]} a #{cuotas_pagadas[-1]}"
            if len(cuotas_pagadas) > 1
            else f"Pago cuota #{primera_cuota[1]}"
        )
        if any(not completa for _, _, completa in aplicaciones):
            detalle_cuotas += f" y abono parcial a cuota #{ultima_cuota[1]}"
        result_pago = conn.execute(text("""
            INSERT INTO pagos (
                prestamo_id, fecha_pago, valor, estado, tipo_movimiento, detalle,
                interes_pagado, capital_pagado, saldo_capital_anterior, saldo_capital_nuevo, cuota_numero
            )
            VALUES (
                :id, :fecha, :valor, 'Pagado', 'CUOTA', :detalle,
                :interes_pagado, :capital_pagado, :saldo_capital_anterior, :saldo_capital_nuevo, :cuota_numero
            )
            RETURNING id_pago
        """), {
            "id": prestamo_id,
            "fecha": fecha_pago.isoformat(),
            "valor": valor_pago,
            "detalle": detalle_cuotas,
            "interes_pagado": interes_total,
            "capital_pagado": capital_total,
            "saldo_capital_anterior": saldo_capital_actual,
            "saldo_capital_nuevo": nuevo_saldo_capital,
            "cuota_numero": primera_cuota[1]
        })
        id_pago = result_pago.fetchone()[0]
        for cuota, valor_aplicado, completa in aplicaciones:
            id_cuota, _, valor_cuota_actual, _, _ = cuota
            conn.execute(text("""
                INSERT INTO pagos_cuotas (id_pago, id_cuota, valor_aplicado)
                VALUES (:id_pago, :id_cuota, :valor_aplicado)
            """), {"id_pago": id_pago, "id_cuota": id_cuota, "valor_aplicado": valor_aplicado})
            if completa:
                conn.execute(text("UPDATE cuotas SET estado = 'Pagada' WHERE id_cuota = :id_cuota"), {"id_cuota": id_cuota})
            else:
                saldo_cuota = normalizar_decimal(valor_cuota_actual) - valor_aplicado
                conn.execute(text("""
                    UPDATE cuotas
                    SET estado = 'Parcial',
                        valor_cuota = :saldo_cuota
                    WHERE id_cuota = :id_cuota
                """), {"id_cuota": id_cuota, "saldo_cuota": saldo_cuota})
        conn.execute(text("UPDATE prestamos SET saldo_capital = :saldo_capital WHERE id = :id"), {"saldo_capital": nuevo_saldo_capital, "id": prestamo_id})
        actualizar_estado_prestamo(conn, prestamo_id)
        finalizado = int(conn.execute(text("""
            SELECT COUNT(*)
            FROM cuotas
            WHERE prestamo_id = :id AND estado <> 'Pagada'
        """), {"id": prestamo_id}).scalar() or 0) == 0
        conn.commit()
        clear_app_caches()
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
            cuota_nro=f"{primera_cuota[1]}-{ultima_cuota[1]}" if primera_cuota[1] != ultima_cuota[1] else primera_cuota[1],
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
                    cuota_nro=f"{primera_cuota[1]}-{ultima_cuota[1]}" if primera_cuota[1] != ultima_cuota[1] else primera_cuota[1],
                    fecha_pago=fecha_pago.isoformat(),
                    valor=valor_pago
                )
            )
            if finalizado:
                cierre_ok, cierre_error = enviar_correo_cierre_credito(prestamo_id, nombre_cliente, correo_cliente, fecha_pago, valor_pago)
                correo_ok = correo_ok and cierre_ok
                if not cierre_ok:
                    correo_error = cierre_error
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
        "cuota": primera_cuota[1],
        "cuota_final": ultima_cuota[1],
        "cuotas_aplicadas": len([1 for _, _, completa in aplicaciones if completa]),
        "parcial": any(not completa for _, _, completa in aplicaciones),
        "valor": valor_pago,
        "correo": correo_ok,
        "tiene_correo": bool(correo_cliente),
        "correo_error": correo_error,
        "finalizado": finalizado
    }
def registrar_abono_capital(prestamo_id, fecha_pago, valor_abono):
    valor_abono = normalizar_decimal(valor_abono)
    if valor_abono <= 0:
        return {"ok": False, "error": "El abono a capital debe ser mayor a cero"}
    with get_conn() as conn:
        prestamo_db = conn.execute(text("""
            SELECT id, cliente_cedula, monto_original, COALESCE(saldo_capital, monto_original) AS saldo_capital,
                   COALESCE(tasa_mensual, 0) AS tasa_mensual, COALESCE(interes_acumulado, 0) AS interes_acumulado,
                   valor_cuota, tipo, tipo_credito, fecha_proximo_interes
            FROM prestamos
            WHERE id = :id
        """), {"id": prestamo_id}).mappings().first()
        if not prestamo_db:
            return {"ok": False, "error": "No se pudo obtener el préstamo"}
        saldo_capital_actual = normalizar_decimal(prestamo_db["saldo_capital"])
        if valor_abono >= saldo_capital_actual:
            return {"ok": False, "error": "El abono a capital no puede ser igual o mayor al saldo capital actual"}
        nuevo_saldo_capital = saldo_capital_actual - valor_abono

        if es_credito_interes_libre_row(prestamo_db):
            result_pago = conn.execute(text("""
                INSERT INTO pagos (
                    prestamo_id, fecha_pago, valor, estado, tipo_movimiento, detalle,
                    interes_pagado, capital_pagado, saldo_capital_anterior, saldo_capital_nuevo, cuota_numero
                )
                VALUES (
                    :id, :fecha, :valor, 'Pagado', 'ABONO_CAPITAL', :detalle,
                    0, :capital_pagado, :saldo_capital_anterior, :saldo_capital_nuevo, NULL
                )
                RETURNING id_pago
            """), {
                "id": prestamo_id,
                "fecha": fecha_pago.isoformat(),
                "valor": valor_abono,
                "detalle": f"Abono a capital interés libre por {valor_abono}",
                "capital_pagado": valor_abono,
                "saldo_capital_anterior": saldo_capital_actual,
                "saldo_capital_nuevo": nuevo_saldo_capital,
            })
            id_pago = result_pago.fetchone()[0]
            conn.execute(text("""
                UPDATE prestamos
                SET saldo_capital = :saldo_capital,
                    valor_cuota = ROUND(:saldo_capital * tasa_mensual, 2)
                WHERE id = :id
            """), {"saldo_capital": nuevo_saldo_capital, "id": prestamo_id})
            conn.commit()
            clear_app_caches()
            cliente = obtener_datos_cliente(conn, prestamo_db["cliente_cedula"])
            nombre_cliente = cliente[0] if cliente else "Cliente"
            correo_cliente = (cliente[1] or "").strip() if cliente else ""
            interes_pendiente = normalizar_decimal(prestamo_db["interes_acumulado"])
            fecha_proximo_interes = prestamo_db.get("fecha_proximo_interes")
            nuevo_interes_30 = (nuevo_saldo_capital * Decimal(str(prestamo_db["tasa_mensual"] or 0))).quantize(Decimal("0.01"))

            pdf = None
            correo_ok = False
            correo_error = None
            try:
                pdf = generar_recibo_pdf(prestamo_id, nombre_cliente, prestamo_db["monto_original"], fecha_pago.isoformat(), valor_abono, titulo="RECIBO DE ABONO A CAPITAL", subtitulo="ABONO A CAPITAL")
                kwargs = dict(
                    prestamo_id=prestamo_id,
                    tipo_credito="Interés libre",
                    tipo_credito_codigo="interes_libre",
                    fecha_pago=fecha_pago.isoformat(),
                    capital_anterior=saldo_capital_actual,
                    valor=valor_abono,
                    saldo_capital=nuevo_saldo_capital,
                    interes_pendiente=interes_pendiente,
                    fecha_proximo_interes=fecha_proximo_interes,
                )
                cuerpo = construir_cuerpo_correo("RECIBO_ABONO", nombre_cliente, **kwargs)
                html_correo = construir_html_correo("RECIBO_ABONO", nombre_cliente, **kwargs)
                if correo_cliente:
                    correo_ok, correo_error = enviar_pdf_por_correo(
                        correo_cliente,
                        f"CREDDT CRNTECH | Abono a capital crédito {prestamo_id}",
                        cuerpo,
                        pdf,
                        f"abono_capital_{prestamo_id}.pdf",
                        html_override=html_correo
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
                "nueva_cuota": nuevo_interes_30,
                "saldo_capital": nuevo_saldo_capital,
                "interes_libre": True,
                "correo": correo_ok,
                "tiene_correo": bool(correo_cliente),
                "correo_error": correo_error
            }

        cuotas_pendientes = conn.execute(text("""
            SELECT id_cuota, nro_cuota
            FROM cuotas
            WHERE prestamo_id = :id
              AND estado <> 'Pagada'
            ORDER BY nro_cuota ASC
        """), {"id": prestamo_id}).fetchall()
        if not cuotas_pendientes:
            return {"ok": False, "error": "No hay cuotas pendientes para recalcular"}
        cuotas_restantes = len(cuotas_pendientes)
        nueva_cuota = Decimal(str(calcular_cuota_amortizada(nuevo_saldo_capital, prestamo_db["tasa_mensual"], cuotas_restantes))).quantize(Decimal("0.01"))
        result_pago = conn.execute(text("""
            INSERT INTO pagos (
                prestamo_id, fecha_pago, valor, estado, tipo_movimiento, detalle,
                interes_pagado, capital_pagado, saldo_capital_anterior, saldo_capital_nuevo, cuota_numero
            )
            VALUES (
                :id, :fecha, :valor, 'Pagado', 'ABONO_CAPITAL', :detalle,
                :interes_pagado, :capital_pagado, :saldo_capital_anterior, :saldo_capital_nuevo, :cuota_numero
            )
            RETURNING id_pago
        """), {
            "id": prestamo_id,
            "fecha": fecha_pago.isoformat(),
            "valor": valor_abono,
            "detalle": f"Abono a capital por {valor_abono}",
            "interes_pagado": Decimal("0.00"),
            "capital_pagado": valor_abono,
            "saldo_capital_anterior": saldo_capital_actual,
            "saldo_capital_nuevo": nuevo_saldo_capital,
            "cuota_numero": cuotas_pendientes[0][1] if cuotas_pendientes else None
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
        clear_app_caches()
        cliente = obtener_datos_cliente(conn, prestamo_db["cliente_cedula"])
    nombre_cliente = cliente[0] if cliente else "Cliente"
    correo_cliente = (cliente[1] or "").strip() if cliente else ""
    pdf = None
    correo_ok = False
    correo_error = None
    try:
        pdf = generar_recibo_pdf(prestamo_id, nombre_cliente, prestamo_db["monto_original"], fecha_pago.isoformat(), valor_abono, titulo="RECIBO DE ABONO A CAPITAL", subtitulo="ABONO A CAPITAL")
        kwargs = dict(
            prestamo_id=prestamo_id,
            tipo_credito=prestamo_db.get("tipo"),
            fecha_pago=fecha_pago.isoformat(),
            capital_anterior=saldo_capital_actual,
            valor=valor_abono,
            saldo_capital=nuevo_saldo_capital,
            nueva_cuota=nueva_cuota,
            cuotas_pendientes=cuotas_restantes
        )
        cuerpo = construir_cuerpo_correo("RECIBO_ABONO", nombre_cliente, **kwargs)
        html_correo = construir_html_correo("RECIBO_ABONO", nombre_cliente, **kwargs)
        if correo_cliente:
            correo_ok, correo_error = enviar_pdf_por_correo(
                correo_cliente,
                f"Abono a capital crédito {prestamo_id}",
                cuerpo,
                pdf,
                f"abono_capital_{prestamo_id}.pdf",
                html_override=html_correo
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

        if not BREVO_API_KEY:
            return False, "Falta configurar BREVO_API_KEY"
        if not BREVO_FROM_EMAIL:
            return False, "Falta configurar BREVO_FROM_EMAIL"

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
estado = load_estado().copy()
if "recordatorios_auto" not in st.session_state:
    try:
        st.session_state.recordatorios_auto = procesar_recordatorios_automaticos()
    except Exception:
        st.session_state.recordatorios_auto = 0
# ==========================
# CALCULAR ALERTAS
# ==========================
clientes_mora, monto_mora = load_mora()
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
# NAVEGACIÓN DE SECCIONES
# ==========================
tab_resumen = SECCION_ACTIVA == "📊 Resumen"
tab_clientes = SECCION_ACTIVA == "👥 Clientes"
tab_creditos = SECCION_ACTIVA == "🆕 Nuevo crédito"
tab_detalle = SECCION_ACTIVA == "📄 Detalle por crédito"
tab_pagos = SECCION_ACTIVA == "💰 Pagos"
tab_proyeccion = SECCION_ACTIVA == "📈 Proyección"
tab_sim = SECCION_ACTIVA == "🧮 Simulador"
# ==========================
# 📊 RESUMEN
# ==========================
if tab_resumen:
    st.subheader("📊 Resumen general")
    if st.session_state.get("recordatorios_auto", 0):
        enviados_auto = st.session_state.get("recordatorios_auto", 0)
        st.success(f"✅ Recordatorios automáticos enviados en esta sesión: {enviados_auto}")

    show_flash("sistema_msg")
    kpis_fin = load_kpis_financieros()
    capital_colocado = float(kpis_fin.get("capital_colocado", 0) or 0)
    capital_recuperado = float(kpis_fin.get("capital_recuperado", 0) or 0)
    interes_cobrado = float(kpis_fin.get("interes_cobrado", 0) or 0)
    capital_vivo = float(kpis_fin.get("capital_vivo", 0) or 0)
    recaudo_acumulado = float(kpis_fin.get("recaudo_acumulado", 0) or 0)
    cuotas_pendientes_total = float(kpis_fin.get("cuotas_pendientes", 0) or 0)
    interes_libre_pendiente = float(kpis_fin.get("interes_libre_pendiente", 0) or 0)
    cartera_mora_total = float(kpis_fin.get("cartera_mora", 0) or 0)
    creditos_activos = int(kpis_fin.get("creditos_activos", 0) or 0)
    contratos_pendientes = int(kpis_fin.get("contratos_pendientes", 0) or 0)
    capital_pendiente_aprobacion = float(kpis_fin.get("capital_pendiente_aprobacion", 0) or 0)
    exposicion_mora_total = 0 if cuotas_pendientes_total <= 0 else (cartera_mora_total / cuotas_pendientes_total) * 100
    recuperacion_capital_pct = float(kpis_fin.get("recuperacion_capital_pct", 0) or 0)
    margen_realizado_pct = float(kpis_fin.get("margen_realizado_pct", 0) or 0)
    diferencia_capital = float(kpis_fin.get("diferencia_capital", 0) or 0)
    diferencia_recaudo = float(kpis_fin.get("diferencia_recaudo", 0) or 0)
    consistencia_ok = bool(kpis_fin.get("consistencia_ok", False))

    ultima_reconciliacion = get_app_meta("finanzas_reconciliadas_at", "Sin ejecutar")
    st.markdown("### 🧭 Control gerencial")
    g1, g2, g3 = st.columns([1.4, 1.4, 1.8])
    with g1:
        st.metric("✅ Recuperación de capital", f"{recuperacion_capital_pct:.2f}%")
    with g2:
        st.metric("📈 Margen realizado", f"{margen_realizado_pct:.2f}%")
    with g3:
        st.caption(f"Última conciliación financiera: {ultima_reconciliacion}")
        if ES_ADMIN and st.button("🔄 Reconciliar histórico financiero", key="btn_reconciliar_finanzas", disabled=st.session_state.get("app_busy", False)):
            start_busy("Reconstruyendo histórico financiero...")
            try:
                resumen_recon = reconstruir_historial_financiero()
                set_flash(
                    "sistema_msg",
                    "success",
                    f"✅ Conciliación completada. Préstamos revisados: {resumen_recon['prestamos']} | Pagos recalculados: {resumen_recon['pagos']} | Ajustes negativos detectados: {resumen_recon['ajustes_negativos']}"
                )
                st.rerun()
            except Exception as e:
                st.error(f"❌ No se pudo ejecutar la conciliación financiera: {e}")
            finally:
                stop_busy()

    if consistencia_ok:
        st.success("✅ Los KPI financieros están conciliados. Ya puedes usarlos para decisiones gerenciales con mucha más confianza.")
    else:
        st.warning(
            f"⚠️ Los KPI financieros aún no cierran por completo. Diferencia capital: {pesos(diferencia_capital)} | Diferencia recaudo: {pesos(diferencia_recaudo)}. Ejecuta la conciliación histórica antes de tomar decisiones de retiro de capital o utilidad."
        )

    st.markdown("### 💼 Indicadores financieros")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Capital colocado", pesos(capital_colocado))
    k2.metric("🏦 Capital recuperado", pesos(capital_recuperado))
    k3.metric("📈 Interés cobrado", pesos(interes_cobrado))
    k4.metric("💳 Capital vivo", pesos(capital_vivo))

    st.markdown("### ⚙️ Indicadores operativos")
    o1, o2, o3, o4, o5 = st.columns(5)
    o1.metric("✅ Recaudo acumulado", pesos(recaudo_acumulado))
    o2.metric("⏳ Cuotas pendientes", pesos(cuotas_pendientes_total))
    o3.metric("🧾 Interés libre pendiente", pesos(interes_libre_pendiente))
    o4.metric("🚨 Cartera en mora", pesos(cartera_mora_total))
    o5.metric("📄 Créditos activos", creditos_activos)

    if contratos_pendientes > 0:
        st.info(f"ℹ️ Tienes {contratos_pendientes} contrato(s) pendiente(s) por aceptación, equivalentes a {pesos(capital_pendiente_aprobacion)}. No se incluyen en los KPI financieros hasta que el contrato sea aceptado.")

    st.divider()
    df = estado[estado["estado"] != "Anulado"].copy()
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
    a1, a2, a3 = st.columns(3)
    a1.metric("👥 Clientes en mora", clientes_mora)
    a2.metric("💸 Monto en mora", pesos(cartera_mora_total))
    a3.metric("📌 Exposición en mora", f"{exposicion_mora_total:.1f}%")

    detalle_mora_df = load_detalle_mora()
    if detalle_mora_df.empty:
        st.info("✅ No hay clientes en mora actualmente.")
    else:
        detalle_mora_show = detalle_mora_df.sort_values(["cuotas_en_mora", "monto_en_mora"], ascending=[False, False]).copy()
        detalle_mora_show["monto_en_mora"] = detalle_mora_show["monto_en_mora"].apply(pesos)
        detalle_mora_show["exposicion_en_mora"] = detalle_mora_show["exposicion_en_mora"].apply(pesos)
        detalle_mora_show = detalle_mora_show[["id", "cliente", "cuotas_en_mora", "monto_en_mora", "exposicion_en_mora"]].rename(columns={
            "id": "Crédito",
            "cliente": "Cliente",
            "cuotas_en_mora": "Cuotas en mora",
            "monto_en_mora": "Monto en mora",
            "exposicion_en_mora": "Exposición en mora"
        })
        st.dataframe(detalle_mora_show, use_container_width=True, hide_index=True)

    # ==========================
    # 🔎 CONSULTA MENSUAL
    # ==========================
    st.divider()
    st.subheader("🔎 Consulta mensual (corte 02 → 02)")
    meses_disponibles = pd.date_range("2025-12-01", "2030-12-01", freq="MS").strftime("%Y-%m").tolist()
    mes_actual = hoy_local().strftime("%Y-%m")
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

    cuotas_df = load_cuotas_periodo(inicio.date().isoformat(), fin.date().isoformat()).copy()
    # Filtro defensivo: evita que cuotas de créditos anulados/cancelados se pinten como tarjetas
    # aunque queden cuotas pendientes antiguas en la tabla cuotas.
    if not cuotas_df.empty:
        if "estado_credito" in cuotas_df.columns:
            cuotas_df = cuotas_df[cuotas_df["estado_credito"].astype(str).str.strip().str.lower().eq("activo")]
        if "contrato_cancelado" in cuotas_df.columns:
            cuotas_df = cuotas_df[pd.to_numeric(cuotas_df["contrato_cancelado"], errors="coerce").fillna(0).eq(0)]

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

        buscar_detalle = st.text_input(
            "Buscar cliente en este detalle",
            placeholder="Escribe el nombre del cliente...",
            key=f"buscar_detalle_{st.session_state.detalle}"
        )

        if buscar_detalle.strip():
            df_detalle = df_detalle[df_detalle["cliente"].astype(str).str.contains(buscar_detalle.strip(), case=False, na=False)]

        st.caption(f"Mostrando {len(df_detalle)} cuota(s) en este detalle.")

        if df_detalle.empty:
            st.info("No hay cuotas para mostrar con el filtro actual.")
        else:
            cols = st.columns(3)
            for i,r in enumerate(df_detalle.itertuples()):
                with cols[i%3]:
                    if r.estado == "Pagada":
                        estado_label = "Pagada"
                        estado_icono = "🟢"
                        estado_class = "cuota-status-pagada"
                    elif r.estado == "Parcial":
                        estado_label = "Parcial"
                        estado_icono = "🟡"
                        estado_class = "cuota-status-parcial"
                    else:
                        estado_label = "Pendiente"
                        estado_icono = "🔴"
                        estado_class = "cuota-status-pendiente"

                    st.markdown(f"""
                    <div class="cuota-card">
                        <div class="cuota-card-title">{r.cliente}</div>
                        <div class="cuota-card-meta">Cuota #{r.nro_cuota} · {r.fecha_vencimiento}</div>
                        <div class="cuota-card-value">{pesos(r.valor_cuota)}</div>
                        <div class="cuota-status {estado_class}">{estado_icono} {estado_label}</div>
                    </div>
                    """, unsafe_allow_html=True)
# ==========================
# 📈 PROYECCIÓN
# ==========================
if tab_proyeccion:
    st.subheader("📈 Proyección mensual")
    st.caption("Planea el próximo corte sin saturar el resumen: meta de recaudo, reinversión, caja, gerencia y créditos sugeridos.")

    hoy = hoy_local()
    if hoy.month == 12:
        siguiente_year, siguiente_month = hoy.year + 1, 1
    else:
        siguiente_year, siguiente_month = hoy.year, hoy.month + 1

    meses_disponibles_proy = pd.date_range("2025-12-01", "2030-12-01", freq="MS").strftime("%Y-%m").tolist()
    mes_siguiente_default = f"{siguiente_year:04d}-{siguiente_month:02d}"
    index_proy = meses_disponibles_proy.index(mes_siguiente_default) if mes_siguiente_default in meses_disponibles_proy else 0

    st.markdown("### ⚙️ Parámetros de planeación")
    cparam1, cparam2, cparam3, cparam4 = st.columns(4)
    with cparam1:
        mes_proyeccion = st.selectbox("Mes a proyectar", meses_disponibles_proy, index=index_proy, key="mes_proyeccion")
    with cparam2:
        meta_mensual = st.number_input(
            "Meta mínima de recaudo",
            min_value=0.0,
            step=100000.0,
            value=float(get_app_meta("proy_meta_mensual", 6000000) or 6000000),
            key="proy_meta_mensual_input"
        )
    with cparam3:
        valor_express_ref = st.number_input(
            "Valor promedio crédito express",
            min_value=0.0,
            step=50000.0,
            value=float(get_app_meta("proy_valor_express", 700000) or 700000),
            key="proy_valor_express_input"
        )
    with cparam4:
        valor_normal_ref = st.number_input(
            "Valor promedio crédito normal",
            min_value=0.0,
            step=50000.0,
            value=float(get_app_meta("proy_valor_normal", 1800000) or 1800000),
            key="proy_valor_normal_input"
        )

    pcol1, pcol2, pcol3, pcol4 = st.columns(4)
    with pcol1:
        pct_reinvertir = st.number_input(
            "% volver a prestar",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            value=float(get_app_meta("proy_pct_reinvertir", 70) or 70),
            key="proy_pct_reinvertir_input"
        )
    with pcol2:
        pct_caja = st.number_input(
            "% guardar en caja",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            value=float(get_app_meta("proy_pct_caja", 20) or 20),
            key="proy_pct_caja_input"
        )
    with pcol3:
        pct_gerencia = st.number_input(
            "% gerencia",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            value=float(get_app_meta("proy_pct_gerencia", 10) or 10),
            key="proy_pct_gerencia_input"
        )
    with pcol4:
        total_pct = pct_reinvertir + pct_caja + pct_gerencia
        st.metric("Total distribución", f"{total_pct:.0f}%")

    if abs(total_pct - 100) > 0.01:
        st.warning("⚠️ La distribución debe sumar 100%. Ajusta reinversión, caja y gerencia antes de usar la recomendación.")
    elif ES_ADMIN:
        if st.button("💾 Guardar parámetros", key="btn_guardar_parametros_proyeccion"):
            with get_conn() as conn:
                set_app_meta(conn, "proy_meta_mensual", meta_mensual)
                set_app_meta(conn, "proy_valor_express", valor_express_ref)
                set_app_meta(conn, "proy_valor_normal", valor_normal_ref)
                set_app_meta(conn, "proy_pct_reinvertir", pct_reinvertir)
                set_app_meta(conn, "proy_pct_caja", pct_caja)
                set_app_meta(conn, "proy_pct_gerencia", pct_gerencia)
                conn.commit()
            st.success("✅ Parámetros de proyección guardados.")

    year_proy, month_proy = map(int, mes_proyeccion.split("-"))
    if year_proy == 2025 and month_proy == 12:
        inicio_proy = datetime(2025, 12, 15)
        fin_proy = datetime(2026, 1, 1)
    elif year_proy == 2026 and month_proy == 1:
        inicio_proy = datetime(2026, 1, 1)
        fin_proy = datetime(2026, 2, 2)
    else:
        inicio_proy = datetime(year_proy, month_proy, 3)
        fin_proy = datetime(year_proy + (month_proy == 12), 1 if month_proy == 12 else month_proy + 1, 2)

    cuotas_proy = load_cuotas_proyeccion(inicio_proy.date().isoformat(), fin_proy.date().isoformat()).copy()
    # Filtro defensivo para que la proyección no use cuotas de créditos anulados/cancelados.
    if not cuotas_proy.empty:
        if "estado_credito" in cuotas_proy.columns:
            cuotas_proy = cuotas_proy[cuotas_proy["estado_credito"].astype(str).str.strip().str.lower().eq("activo")]
        if "contrato_cancelado" in cuotas_proy.columns:
            cuotas_proy = cuotas_proy[pd.to_numeric(cuotas_proy["contrato_cancelado"], errors="coerce").fillna(0).eq(0)]
        cuotas_proy["valor_cuota"] = pd.to_numeric(cuotas_proy["valor_cuota"], errors="coerce").fillna(0)

    recaudo_proyectado = float(cuotas_proy["valor_cuota"].sum()) if not cuotas_proy.empty else 0.0
    faltante_meta = max(float(meta_mensual or 0) - recaudo_proyectado, 0)
    excedente_meta = max(recaudo_proyectado - float(meta_mensual or 0), 0)

    capital_reinvertir = recaudo_proyectado * (pct_reinvertir / 100)
    valor_caja = recaudo_proyectado * (pct_caja / 100)
    valor_gerencia = recaudo_proyectado * (pct_gerencia / 100)

    express_necesarios_reinversion = math.ceil(capital_reinvertir / valor_express_ref) if valor_express_ref > 0 and capital_reinvertir > 0 else 0
    normales_necesarios_reinversion = math.ceil(capital_reinvertir / valor_normal_ref) if valor_normal_ref > 0 and capital_reinvertir > 0 else 0
    express_necesarios_faltante = math.ceil(faltante_meta / valor_express_ref) if valor_express_ref > 0 and faltante_meta > 0 else 0
    normales_necesarios_faltante = math.ceil(faltante_meta / valor_normal_ref) if valor_normal_ref > 0 and faltante_meta > 0 else 0

    st.divider()
    st.markdown(f"### 📅 Corte proyectado: {inicio_proy.date().isoformat()} → {fin_proy.date().isoformat()}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Recaudo proyectado", pesos(recaudo_proyectado))
    m2.metric("Meta mínima", pesos(meta_mensual))
    m3.metric("Faltante para meta", pesos(faltante_meta))
    m4.metric("Excedente sobre meta", pesos(excedente_meta))

    d1, d2, d3 = st.columns(3)
    d1.metric("🔁 Volver a prestar", pesos(capital_reinvertir), f"{pct_reinvertir:.0f}%")
    d2.metric("🏦 Guardar en caja", pesos(valor_caja), f"{pct_caja:.0f}%")
    d3.metric("👔 Gerencia", pesos(valor_gerencia), f"{pct_gerencia:.0f}%")

    st.markdown("### 🎯 Recomendación del sistema")
    if recaudo_proyectado <= 0:
        st.error("🚨 No hay recaudo proyectado para este corte. Revisa si existen cuotas pendientes con vencimiento dentro del período seleccionado.")
    elif faltante_meta > 0:
        st.warning(
            f"⚠️ Para no bajar de {pesos(meta_mensual)}, faltan {pesos(faltante_meta)} en el corte proyectado. "
            f"Como referencia, necesitas aproximadamente {express_necesarios_faltante} crédito(s) express de {pesos(valor_express_ref)} "
            f"o {normales_necesarios_faltante} crédito(s) normal(es) de {pesos(valor_normal_ref)}."
        )
    else:
        st.success(
            f"✅ Con la cartera actual sí alcanzas la meta mínima. Puedes planear reinvertir {pesos(capital_reinvertir)} "
            f"sin bajar del objetivo de {pesos(meta_mensual)}."
        )

    r1, r2 = st.columns(2)
    with r1:
        st.markdown(f"""
        <div class="creddt-card" style="padding:18px 18px;margin-top:6px;">
            <div class="creddt-strong" style="font-size:18px;font-weight:900;">Escenario solo Express</div>
            <div class="creddt-muted" style="font-size:13px;margin-top:5px;">Para colocar el capital de reinversión recomendado</div>
            <div style="font-size:32px;font-weight:900;margin-top:12px;">{express_necesarios_reinversion}</div>
            <div class="creddt-muted">crédito(s) de {pesos(valor_express_ref)}</div>
        </div>
        """, unsafe_allow_html=True)
    with r2:
        st.markdown(f"""
        <div class="creddt-card" style="padding:18px 18px;margin-top:6px;">
            <div class="creddt-strong" style="font-size:18px;font-weight:900;">Escenario solo Normal</div>
            <div class="creddt-muted" style="font-size:13px;margin-top:5px;">Para colocar el capital de reinversión recomendado</div>
            <div style="font-size:32px;font-weight:900;margin-top:12px;">{normales_necesarios_reinversion}</div>
            <div class="creddt-muted">crédito(s) de {pesos(valor_normal_ref)}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 🧩 Simulador rápido de mezcla")
    mix1, mix2, mix3 = st.columns(3)
    with mix1:
        mix_express = st.number_input("Cantidad express", min_value=0, step=1, value=express_necesarios_reinversion, key="mix_express_proy")
    with mix2:
        mix_normal = st.number_input("Cantidad normal", min_value=0, step=1, value=0, key="mix_normal_proy")
    with mix3:
        capital_mix = (mix_express * valor_express_ref) + (mix_normal * valor_normal_ref)
        diferencia_mix = capital_mix - capital_reinvertir
        st.metric("Capital simulado", pesos(capital_mix), pesos(diferencia_mix))

    if capital_mix >= capital_reinvertir and capital_reinvertir > 0:
        st.success(f"✅ La mezcla cubre la reinversión sugerida de {pesos(capital_reinvertir)}.")
    elif capital_reinvertir > 0:
        st.info(f"ℹ️ A esta mezcla le faltan {pesos(abs(diferencia_mix))} para cubrir la reinversión sugerida.")

    st.markdown("### 📋 Cuotas que soportan esta proyección")
    if cuotas_proy.empty:
        st.info("No hay cuotas pendientes para el corte seleccionado.")
    else:
        resumen_tipo = cuotas_proy.groupby("tipo_credito", dropna=False)["valor_cuota"].sum().reset_index()
        resumen_tipo["valor_cuota"] = resumen_tipo["valor_cuota"].apply(pesos)
        resumen_tipo = resumen_tipo.rename(columns={"tipo_credito": "Tipo de crédito", "valor_cuota": "Recaudo proyectado"})
        st.dataframe(resumen_tipo, use_container_width=True, hide_index=True)

        detalle_proy = cuotas_proy[["fecha_vencimiento", "cliente", "credito", "nro_cuota", "tipo_credito", "valor_cuota", "estado_cuota"]].copy()
        detalle_proy["valor_cuota"] = detalle_proy["valor_cuota"].apply(pesos)
        detalle_proy = detalle_proy.rename(columns={
            "fecha_vencimiento": "Fecha vencimiento",
            "cliente": "Cliente",
            "credito": "Crédito",
            "nro_cuota": "Cuota",
            "tipo_credito": "Tipo",
            "valor_cuota": "Valor cuota",
            "estado_cuota": "Estado cuota"
        })
        st.dataframe(detalle_proy, use_container_width=True, hide_index=True)

# ==========================
# 👥 CLIENTES
# ==========================
if tab_clientes:
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
                        max_value=hoy_local(),
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

                    # Streamlit no permite modificar el session_state de un widget
                    # después de haberlo creado. Esta bandera limpia la selección
                    # al inicio del siguiente rerun, antes de instanciar el selectbox.
                    if st.session_state.pop("reset_sel_cliente_gestion", False):
                        st.session_state["sel_cliente_gestion"] = None

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
                                            max_value=hoy_local(),
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
                                                st.session_state["reset_sel_cliente_gestion"] = True
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
                                                st.session_state["reset_sel_cliente_gestion"] = True
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
if tab_creditos:
            st.subheader("🆕 Registrar nuevo crédito")
            show_flash("credito_msg")
            show_flash("contrato_msg")

            with get_conn() as conn:
                clientes_credito_df = pd.read_sql(
                    text("SELECT cedula, nombres, apellidos, correo FROM clientes ORDER BY nombres, apellidos"),
                    conn
                )

            cred_tab1, cred_tab2, cred_tab_interes_libre, cred_tab3 = st.tabs([
                "💳 Crédito normal",
                "⚡ Crédito express",
                "🧾 Crédito interés libre",
                "📨 Contratos pendientes"
            ])

            if clientes_credito_df.empty:
                st.info("ℹ️ Primero registra un cliente para crear créditos.")
            else:
                cliente_options = [None] + clientes_credito_df["cedula"].tolist()
                nombre_cliente = lambda x: "Selecciona un cliente" if x is None else f"{x} — {clientes_credito_df.loc[clientes_credito_df['cedula']==x, 'nombres'].iloc[0]} {clientes_credito_df.loc[clientes_credito_df['cedula']==x, 'apellidos'].iloc[0]}"

                if st.session_state.pop("reset_cliente_normal_credito", False):
                    st.session_state["cliente_normal_credito"] = None
                if st.session_state.pop("reset_cliente_express_credito", False):
                    st.session_state["cliente_express_credito"] = None
                if st.session_state.pop("reset_cliente_interes_libre", False):
                    st.session_state["cliente_interes_libre_credito"] = None

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
                        fecha_inicio_normal = st.date_input("Fecha de inicio", value=hoy_local(), key="fecha_inicio_normal")
                        confirmar_envio_normal = st.checkbox(
                            "Confirmo que validé cliente, monto, correo y autorizo el envío del contrato",
                            key="confirmar_envio_normal"
                        )
                        st.caption("La simulación final se procesa al registrar el crédito.")
                        submit_normal = st.form_submit_button("Registrar crédito normal", type="primary", disabled=st.session_state.get("app_busy", False))
                    if submit_normal:
                        if cliente_normal is None:
                            st.warning("ℹ️ Selecciona un cliente para registrar un crédito normal.")
                        elif not confirmar_envio_normal:
                            st.warning("ℹ️ Debes confirmar la validación antes de enviar el contrato.")
                        else:
                            start_busy("Creando crédito normal...")
                            try:
                                ok_c, err_c, prestamo_creado = crear_credito_db(cliente_normal, monto_normal_new, cuotas_normal_new, frecuencia_normal_new, "Normal", fecha_inicio_normal)
                                if ok_c:
                                    st.session_state["reset_cliente_normal_credito"] = True
                                    if not err_c:
                                        set_flash("credito_msg", "success", f"✅ Crédito {prestamo_creado['id']} creado y contrato enviado correctamente")
                                    else:
                                        set_flash("credito_msg", "warning", f"⚠️ Crédito {prestamo_creado['id']} creado. Observación del contrato: {err_c}")
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
                        fecha_inicio_express = st.date_input("Fecha de inicio", value=hoy_local(), key="fecha_inicio_express")
                        confirmar_envio_express = st.checkbox(
                            "Confirmo que validé cliente, monto, correo y autorizo el envío del contrato",
                            key="confirmar_envio_express"
                        )
                        st.caption(f"Crédito express a {cuotas_express_new} cuotas de frecuencia {frecuencia_express_new.lower()}.")
                        submit_express = st.form_submit_button("Registrar crédito express", type="primary", disabled=st.session_state.get("app_busy", False))
                    if submit_express:
                        if cliente_express is None:
                            st.warning("ℹ️ Selecciona un cliente para registrar un crédito express.")
                        elif not confirmar_envio_express:
                            st.warning("ℹ️ Debes confirmar la validación antes de enviar el contrato.")
                        else:
                            start_busy("Creando crédito express...")
                            try:
                                ok_c, err_c, prestamo_creado = crear_credito_db(cliente_express, monto_express_new, cuotas_express_new, frecuencia_express_new, "Express", fecha_inicio_express)
                                if ok_c:
                                    st.session_state["reset_cliente_express_credito"] = True
                                    if not err_c:
                                        set_flash("credito_msg", "success", f"✅ Crédito {prestamo_creado['id']} creado y contrato enviado correctamente")
                                    else:
                                        set_flash("credito_msg", "warning", f"⚠️ Crédito {prestamo_creado['id']} creado. Observación del contrato: {err_c}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {err_c}")
                            finally:
                                stop_busy()



                with cred_tab_interes_libre:
                    with st.form("form_credito_interes_libre", clear_on_submit=True):
                        cliente_interes_libre = st.selectbox(
                            "Cliente",
                            cliente_options,
                            key="cliente_interes_libre_credito",
                            format_func=nombre_cliente,
                            index=0
                        )
                        monto_interes_libre = st.number_input("Capital a prestar", min_value=0.0, step=100000.0, value=1000000.0, key="nuevo_monto_interes_libre")
                        tasa_interes_libre_pct = st.number_input("Tasa de interés cada 30 días (%)", min_value=0.0, max_value=100.0, step=0.5, value=10.0, key="nuevo_tasa_interes_libre")
                        fecha_inicio_interes_libre = st.date_input("Fecha de desembolso/inicio", value=hoy_local(), key="fecha_inicio_interes_libre")
                        interes_30 = monto_interes_libre * (tasa_interes_libre_pct / 100)
                        proximo_interes = fecha_inicio_interes_libre + timedelta(days=30)
                        st.info(f"Interés estimado cada 30 días: {pesos(interes_30)} · Próximo pago: {proximo_interes.isoformat()}")
                        confirmar_envio_interes_libre = st.checkbox(
                            "Confirmo que validé cliente, capital, tasa, correo y autorizo el envío del contrato",
                            key="confirmar_envio_interes_libre"
                        )
                        st.caption("Este modelo no crea cuotas programadas. Controla capital, interés causado y próximo pago de interés cada 30 días.")
                        submit_interes_libre = st.form_submit_button("Registrar crédito interés libre", type="primary", disabled=st.session_state.get("app_busy", False))
                    if submit_interes_libre:
                        if cliente_interes_libre is None:
                            st.warning("ℹ️ Selecciona un cliente para registrar un crédito interés libre.")
                        elif not confirmar_envio_interes_libre:
                            st.warning("ℹ️ Debes confirmar la validación antes de enviar el contrato.")
                        else:
                            start_busy("Creando crédito interés libre...")
                            try:
                                ok_c, err_c, prestamo_creado = crear_credito_interes_libre_db(cliente_interes_libre, monto_interes_libre, tasa_interes_libre_pct, fecha_inicio_interes_libre)
                                if ok_c:
                                    st.session_state["reset_cliente_interes_libre"] = True
                                    if not err_c:
                                        set_flash("credito_msg", "success", f"✅ Crédito interés libre {prestamo_creado['id']} creado y contrato enviado correctamente")
                                    else:
                                        set_flash("credito_msg", "warning", f"⚠️ Crédito interés libre {prestamo_creado['id']} creado. Observación del contrato: {err_c}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {err_c}")
                            finally:
                                stop_busy()

                with cred_tab3:
                    pendientes_df = estado[(estado["estado"] == "Pendiente") & (estado["contrato_cancelado"].fillna(0) == 0)].copy()

                    if pendientes_df.empty:
                        st.success("✅ No hay créditos pendientes de envío de contrato.")
                    else:
                        st.caption("Aquí puedes reenviar manualmente el contrato a créditos pendientes o anularlo con trazabilidad y motivo.")
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
                            <div class="creddt-card" style="padding:14px 16px;margin-bottom:10px;">
                                <div class="creddt-strong" style="font-size:18px;font-weight:800;">Crédito {fila_p['id']}</div>
                                <div class="creddt-muted" style="font-size:13px;margin-top:4px;">{fila_p['cliente']} · {fila_p['tipo']} · Estado: {fila_p['estado']}</div>
                            </div>
                            """, unsafe_allow_html=True)

                            r1, r2, r3, r4 = st.columns(4)
                            r1.metric("Capital", pesos(fila_p["monto_original"]))
                            r2.metric("Cuota / interés 30 días", pesos(fila_p["valor_cuota"]))
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

                            confirmar_reenvio = st.checkbox(
                                "Confirmo que validé cliente, correo y autorizo el envío del contrato",
                                key=f"confirmar_reenvio_{fila_p['id']}"
                            )

                            motivo_anulacion = st.text_area(
                                "Motivo de anulación del contrato",
                                placeholder="Ejemplo: Se envió a un cliente equivocado por error administrativo.",
                                key=f"motivo_anulacion_{fila_p['id']}",
                                height=100
                            )

                            col_accion_1, col_accion_2 = st.columns(2)

                            with col_accion_1:
                                if st.button("📨 Enviar contrato manual", type="primary", key="btn_enviar_contrato_manual", disabled=st.session_state.get("app_busy", False)):
                                    if not confirmar_reenvio:
                                        set_flash("contrato_msg", "warning", "ℹ️ Debes confirmar la validación antes de reenviar el contrato.")
                                        st.rerun()
                                    start_busy("Enviando contrato manual...")
                                    try:
                                        ok_send, err_send = enviar_contrato_credito(fila_p)
                                        if ok_send:
                                            if err_send:
                                                set_flash("contrato_msg", "warning", f"⚠️ Contrato enviado para el crédito {fila_p['id']}, pero quedó una observación: {err_send}")
                                            else:
                                                set_flash("contrato_msg", "success", f"✅ Contrato enviado correctamente para el crédito {fila_p['id']}. Ahora queda esperando aceptación.")
                                        else:
                                            set_flash("contrato_msg", "warning", f"⚠️ No se pudo enviar el contrato del crédito {fila_p['id']}: {err_send}")
                                    except Exception as e:
                                        set_flash("contrato_msg", "error", f"❌ Error inesperado enviando contrato: {e}")
                                    finally:
                                        stop_busy()
                                    st.rerun()

                            with col_accion_2:
                                if st.button("🚫 Anular contrato", key=f"btn_anular_contrato_{fila_p['id']}", disabled=st.session_state.get("app_busy", False)):
                                    start_busy("Anulando contrato...")
                                    try:
                                        ok_cancel, data_cancel = cancelar_contrato_prestamo(
                                            fila_p["id"],
                                            motivo_anulacion,
                                            usuario=st.session_state.get("usuario")
                                        )
                                        if ok_cancel:
                                            if data_cancel.get("correo"):
                                                set_flash("contrato_msg", "success", f"✅ Contrato {fila_p['id']} anulado y correo enviado al cliente.")
                                            else:
                                                obs = data_cancel.get("correo_error") or "sin detalle adicional"
                                                set_flash("contrato_msg", "warning", f"⚠️ Contrato {fila_p['id']} anulado, pero el correo no se pudo enviar: {obs}")
                                        else:
                                            set_flash("contrato_msg", "error", f"❌ {data_cancel}")
                                    except Exception as e:
                                        set_flash("contrato_msg", "error", f"❌ Error anulando contrato: {e}")
                                    finally:
                                        stop_busy()
                                    st.rerun()

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
if tab_detalle:
            st.subheader("📄 Detalle por crédito")
            st.caption("Consulta la ficha del crédito, su plan de cuotas y sus movimientos. Los anulados quedan separados del historial normal para evitar confusiones.")
            show_flash("detalle_msg")

            saldo_num = pd.to_numeric(estado["saldo"], errors="coerce").fillna(0)
            detalle_activos = estado[(~estado["estado"].isin(["Cancelado", "Anulado"])) & (saldo_num > 0)].copy()
            detalle_cancelados = estado[(estado["estado"] == "Cancelado") | ((~estado["estado"].isin(["Cancelado", "Anulado"])) & (saldo_num <= 0))].copy()
            detalle_anulados = estado[estado["estado"] == "Anulado"].copy()

            det_tab_activos, det_tab_cancelados, det_tab_anulados = st.tabs([
                "🟢 Créditos activos",
                "📚 Cerrados / cancelados",
                "🚫 Contratos anulados"
            ])

            def render_detalle_creditos(df_detalle: pd.DataFrame, empty_msg: str, es_anulado: bool = False):
                if df_detalle.empty:
                    st.info(empty_msg)
                    return

                for _, row in df_detalle.iterrows():
                    with st.expander(f"💳 Préstamo {row['id']} — {row['cliente']}"):
                        estado_contrato = "Aceptado" if int(row.get("contrato_aceptado", 0) or 0) == 1 else "Pendiente"
                        if es_anulado:
                            estado_contrato = "Anulado"

                        st.markdown(f"""
                        <div class="creddt-card" style="padding:14px 16px;margin-bottom:10px;">
                            <div class="creddt-strong" style="font-size:18px;font-weight:800;">Crédito {row['id']}</div>
                            <div class="creddt-muted" style="font-size:13px;margin-top:4px;">{row['cliente']} · {row['tipo']} · {row['estado']} · Frecuencia: {row.get('frecuencia', 'Mensual')} · Contrato: {estado_contrato}</div>
                        </div>
                        """, unsafe_allow_html=True)

                        if es_anulado:
                            motivo_a = row.get("motivo_cancelacion_contrato") or "Sin motivo registrado"
                            fecha_a = row.get("fecha_cancelacion_contrato") or "-"
                            usuario_a = row.get("cancelado_por") or "-"
                            st.error(f"🚫 Contrato anulado. Fecha: {fecha_a} | Usuario: {usuario_a} | Motivo: {motivo_a}")

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
                            auditoria_credito = pd.read_sql(text("""
                                SELECT fecha, accion, usuario, motivo, detalle
                                FROM auditoria_contratos
                                WHERE prestamo_id = :id
                                ORDER BY id DESC
                            """), conn, params={"id": row["id"]})

                        t1, t2, t3 = st.tabs(["📅 Cuotas del crédito", "💸 Movimientos registrados", "🧾 Auditoría contrato"])
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
                        with t3:
                            if auditoria_credito.empty:
                                st.info("Sin auditoría de contrato para este crédito.")
                            else:
                                auditoria_credito = auditoria_credito.rename(columns={
                                    "fecha": "Fecha",
                                    "accion": "Acción",
                                    "usuario": "Usuario",
                                    "motivo": "Motivo",
                                    "detalle": "Detalle"
                                })
                                st.dataframe(auditoria_credito, use_container_width=True, hide_index=True)

            with det_tab_activos:
                render_detalle_creditos(detalle_activos, "ℹ️ No hay créditos activos con saldo pendiente.")
            with det_tab_cancelados:
                render_detalle_creditos(detalle_cancelados, "ℹ️ No hay créditos cerrados o cancelados para mostrar.")
            with det_tab_anulados:
                render_detalle_creditos(detalle_anulados, "ℹ️ No hay contratos anulados para mostrar.", es_anulado=True)
# ==========================
# 💰 PAGOS
# ==========================
if "pago_msg" not in st.session_state:
    st.session_state.pago_msg = None
if "reset_select_prestamo_pago" not in st.session_state:
    st.session_state.reset_select_prestamo_pago = False
if tab_pagos:
            st.subheader("💰 Pagos del crédito")
            st.caption("Aquí solo se muestran créditos activos con saldo pendiente. Los créditos cerrados siguen visibles en Resumen e Historial, pero no interfieren en la operación diaria.")
            activos = estado[(~estado["estado"].isin(["Cancelado", "Anulado"])) & (pd.to_numeric(estado["saldo"], errors="coerce").fillna(0) > 0)].copy()
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
                    # st.tabs no conserva la pestaña activa entre reruns (por ejemplo al registrar
                    # un pago), así que usamos un selector persistido en session_state para que,
                    # cuando la app se refresque tras registrar un movimiento, se quede en la
                    # misma sección donde estaba el usuario en lugar de saltar siempre a la primera.
                    if "pago_subtab_choice" not in st.session_state:
                        st.session_state.pago_subtab_choice = "✅ Pago de cuota"
                    subtab_choice = st.radio(
                        "Sección",
                        ["✅ Pago de cuota", "🏦 Abono a capital"],
                        horizontal=True,
                        key="pago_subtab_choice",
                        label_visibility="collapsed",
                    )


                    if subtab_choice == "✅ Pago de cuota":
                        if getattr(prestamo, "tipo_credito_codigo", "") == "interes_libre":
                            fecha_prox = getattr(prestamo, "fecha_proximo_interes", None) or "-"
                            interes_acum = float(getattr(prestamo, "interes_acumulado", 0) or 0)
                            interes_30 = float(prestamo.saldo_capital or 0) * float(prestamo.tasa_mensual or 0)
                            st.markdown(f"""
                            <div class='creddt-soft-card' style='padding:14px 16px;margin-bottom:12px;'>
                                <div class='creddt-muted' style='font-size:13px;margin-bottom:6px;'>Crédito interés libre</div>
                                <div class='creddt-strong' style='font-size:18px;font-weight:800;'>Próximo pago de interés: {fecha_prox}</div>
                                <div class='creddt-muted' style='font-size:13px;margin-top:4px;'>Interés estimado 30 días: {pesos(interes_30)} · Interés acumulado: {pesos(interes_acum)}</div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Fecha y tipo de movimiento van FUERA del form para que sean reactivos:
                            # al cambiarlos, la app recalcula el interés exacto con la misma fórmula
                            # que usa el backend (prorrateada por días reales), evitando que el valor
                            # sugerido en pantalla no coincida con el que exige el registro del pago.
                            fecha_pago_il = st.date_input("Fecha de pago", value=hoy_local(), key="fecha_pago_interes_libre")
                            modo_pago_il = st.radio(
                                "Movimiento",
                                ["Pagar cuota interés", "Finalizar deuda"],
                                horizontal=True,
                                key="modo_pago_interes_libre"
                            )

                            prestamo_calc = {
                                "saldo_capital": prestamo.saldo_capital,
                                "tasa_mensual": prestamo.tasa_mensual,
                                "interes_acumulado": getattr(prestamo, "interes_acumulado", 0),
                                "fecha_ultimo_corte_interes": getattr(prestamo, "fecha_ultimo_corte_interes", None),
                            }
                            interes_exacto, dias_exactos = calcular_interes_libre_a_fecha(prestamo_calc, fecha_pago_il)
                            saldo_capital_dec = normalizar_decimal(prestamo.saldo_capital)
                            total_cierre_exacto = (interes_exacto + saldo_capital_dec).quantize(Decimal("0.01"))

                            if modo_pago_il == "Pagar cuota interés":
                                st.info(f"Se pagará solo el interés calculado a {dias_exactos} día(s): {pesos(interes_exacto)}. Capital vigente: {pesos(prestamo.saldo_capital)}")
                                valor_a_pagar = interes_exacto
                                modo_backend_il = "interes"
                            else:
                                st.warning(f"Se pagará interés ({pesos(interes_exacto)}) + capital ({pesos(saldo_capital_dec)}) y el crédito quedará cerrado. Total: {pesos(total_cierre_exacto)}")
                                valor_a_pagar = total_cierre_exacto
                                modo_backend_il = "finalizar"

                            st.metric("💵 Valor a registrar", pesos(valor_a_pagar))
                            with st.form("form_pago_interes_libre", clear_on_submit=True):
                                st.caption("El valor se calcula automáticamente según la fecha de pago seleccionada arriba; no se puede editar para evitar descuadres.")
                                submit_pago_il = st.form_submit_button("Registrar movimiento interés libre", type="primary", disabled=st.session_state.get("app_busy", False))
                            if submit_pago_il:
                                start_busy("Aplicando movimiento interés libre...")
                                try:
                                    resultado = registrar_pago_interes_libre(prestamo.id, fecha_pago_il, valor_a_pagar, modo_pago=modo_backend_il)
                                    if resultado.get("ok"):
                                        st.session_state.pago_msg = {"tipo": "INTERES_LIBRE", **resultado}
                                        st.session_state.reset_select_prestamo_pago = True
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {resultado.get('error')}")
                                finally:
                                    stop_busy()
                        elif not proxima_cuota:
                            st.info("ℹ️ Este crédito no tiene cuotas pendientes.")
                        else:
                            st.markdown(f"""
                            <div class='creddt-soft-card' style='padding:14px 16px;margin-bottom:12px;'>
                                <div class='creddt-muted' style='font-size:13px;margin-bottom:6px;'>Próxima cuota pendiente</div>
                                <div class='creddt-strong' style='font-size:18px;font-weight:800;'>Cuota #{proxima_cuota[1]} — {pesos(proxima_cuota[2])}</div>
                                <div class='creddt-muted' style='font-size:13px;margin-top:4px;'>Fecha de vencimiento: {proxima_cuota[3]}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            with st.form("form_pago_cuota", clear_on_submit=True):
                                fecha_pago = st.date_input("📅 Fecha de movimiento", value=hoy_local(), key="fecha_movimiento_pago")
                                submit_pago_cuota = st.form_submit_button("Registrar pago de cuota", type="primary", disabled=st.session_state.get("app_busy", False))
                            if submit_pago_cuota:
                                start_busy("Aplicando pago de cuota...")
                                try:
                                    with st.spinner("⏳ Aplicando pago, por favor espera..."):
                                        resultado = registrar_pago_cuota(prestamo.id, fecha_pago)
                                        if resultado.get("ok"):
                                            st.session_state.pago_msg = {"tipo": "CUOTA", **resultado}
                                            st.session_state.reset_select_prestamo_pago = True
                                            st.rerun()
                                        else:
                                            st.error(f"❌ {resultado.get('error')}")
                                finally:
                                    stop_busy()
                            with get_conn() as conn:
                                cuotas_pendientes_pago = obtener_cuotas_pendientes(conn, prestamo.id)
                            total_pendiente_pago = sum((normalizar_decimal(c[2]) for c in cuotas_pendientes_pago), Decimal("0.00"))
                            st.markdown("#### Pago de varias cuotas")
                            st.caption("Opción adicional para aplicar varias cuotas completas o ingresar el valor recibido y que se aplique desde la cuota pendiente más antigua.")
                            with st.form("form_pago_multiple", clear_on_submit=True):
                                fecha_pago_multi = st.date_input("📅 Fecha de movimiento", value=hoy_local(), key="fecha_movimiento_pago_multi")
                                modo_pago_multi = st.radio(
                                    "Forma de aplicar",
                                    ["Por número de cuotas", "Por valor pagado"],
                                    horizontal=True,
                                    key="modo_pago_multiple"
                                )
                                cantidad_cuotas_multi = 1
                                valor_pago_multi = 0.0
                                if modo_pago_multi == "Por número de cuotas":
                                    cantidad_cuotas_multi = st.number_input(
                                        "Cuotas a pagar",
                                        min_value=1,
                                        max_value=max(1, len(cuotas_pendientes_pago)),
                                        value=1,
                                        step=1,
                                        key="cantidad_cuotas_pago_multi"
                                    )
                                    valor_estimado_multi = sum((normalizar_decimal(c[2]) for c in cuotas_pendientes_pago[:int(cantidad_cuotas_multi)]), Decimal("0.00"))
                                    st.info(f"Se aplicará {pesos(valor_estimado_multi)} a {int(cantidad_cuotas_multi)} cuota(s).")
                                else:
                                    valor_pago_multi = st.number_input(
                                        "Valor recibido",
                                        min_value=0.0,
                                        max_value=float(total_pendiente_pago),
                                        step=1000.0,
                                        value=0.0,
                                        key="valor_pago_multi"
                                    )
                                    st.info(f"Saldo máximo aplicable en cuotas pendientes: {pesos(total_pendiente_pago)}.")
                                submit_pago_multiple = st.form_submit_button("Registrar pago múltiple", disabled=st.session_state.get("app_busy", False))
                            if submit_pago_multiple:
                                start_busy("Aplicando pago múltiple...")
                                try:
                                    with st.spinner("⏳ Aplicando pago múltiple..."):
                                        if modo_pago_multi == "Por número de cuotas":
                                            resultado = registrar_pago_cuotas(prestamo.id, fecha_pago_multi, cantidad_cuotas=int(cantidad_cuotas_multi))
                                        else:
                                            resultado = registrar_pago_cuotas(prestamo.id, fecha_pago_multi, valor_pago_total=valor_pago_multi)
                                        if resultado.get("ok"):
                                            st.session_state.pago_msg = {"tipo": "CUOTA", **resultado}
                                            st.session_state.reset_select_prestamo_pago = True
                                            st.rerun()
                                        else:
                                            st.error(f"❌ {resultado.get('error')}")
                                finally:
                                    stop_busy()

                    elif subtab_choice == "🏦 Abono a capital":
                        st.caption("El abono a capital reduce el saldo del préstamo y recalcula el valor de las cuotas pendientes, manteniendo el número de cuotas restantes.")
                        with st.form("form_abono_capital", clear_on_submit=True):
                            fecha_pago = st.date_input("📅 Fecha de movimiento", value=hoy_local(), key="fecha_movimiento_abono")
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
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {resultado.get('error')}")
                            finally:
                                stop_busy()
            if st.session_state.pago_msg:
                m = st.session_state.pago_msg
                if m["tipo"] == "CUOTA":
                    cuota_txt = f"Cuotas #{m['cuota']} a #{m.get('cuota_final')}" if m.get("cuota_final") and m.get("cuota_final") != m.get("cuota") else f"Cuota #{m['cuota']}"
                    cierre_txt = " | Crédito finalizado y cuenta cerrada" if m.get("finalizado") else ""
                    if m.get("tiene_correo") and m.get("correo"):
                        st.success(f"✅ Pago de cuota registrado y correo enviado - Crédito {m['credito']} | {cuota_txt}{cierre_txt}")
                    elif m.get("tiene_correo") and not m.get("correo"):
                        st.warning(f"⚠️ Pago de cuota registrado, pero el correo no se pudo enviar - Crédito {m['credito']} | {cuota_txt}{cierre_txt}")
                        if m.get("correo_error"):
                            st.error(f"Detalle correo: {m['correo_error']}")
                    else:
                        st.success(f"✅ Pago de cuota registrado - Crédito {m['credito']} | {cuota_txt}{cierre_txt}")
                if m["tipo"] == "INTERES_LIBRE":
                    st.success(
                        f"✅ Pago interés libre registrado - Crédito {m['credito']} | "
                        f"Interés: {pesos(m['interes_pagado'])} | Capital: {pesos(m['capital_pagado'])} | "
                        f"Próximo interés: {m['fecha_proximo_interes']}"
                    )
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
if tab_sim:
            st.subheader("🧮 Simulador de crédito")
            t1, t2, t3 = st.tabs([
                "💳 Crédito normal",
                "⚡ Crédito express",
                "🧾 Interés libre"
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
                        f"📈 Tasa aplicada: **{calcular_tasa_express(frecuencia)*100:.2f}%**"
                    )

            with t3:
                st.markdown("### 🧾 Crédito interés libre")
                monto_il_sim = st.number_input(
                    "Capital a prestar",
                    min_value=100_000,
                    step=100_000,
                    value=1_000_000,
                    key="monto_interes_libre_sim"
                )
                tasa_il_sim = st.number_input(
                    "Tasa de interés cada 30 días (%)",
                    min_value=0.0,
                    max_value=100.0,
                    step=0.5,
                    value=10.0,
                    key="tasa_interes_libre_sim"
                )
                fecha_il_sim = st.date_input("Fecha de desembolso/inicio", value=hoy_local(), key="fecha_interes_libre_sim")
                if st.button("Calcular interés libre"):
                    interes_30 = monto_il_sim * (tasa_il_sim / 100)
                    proximo = fecha_il_sim + timedelta(days=30)
                    st.success(
                        f"📌 Interés a pagar cada 30 días: **{pesos(interes_30)}**\n\n"
                        f"📅 Próximo pago de interés: **{proximo.isoformat()}**\n\n"
                        f"🏦 Capital vigente hasta abono/pago: **{pesos(monto_il_sim)}**"
                    )


# Nota técnica:
# - Crédito Normal y Crédito Express conservan su cálculo original de cuotas.
# - Crédito Interés Libre usa tipo_credito = 'interes_libre', no crea filas en cuotas
#   y programa el próximo pago de interés cada 30 días desde el desembolso/inicio.
