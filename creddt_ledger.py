"""Imputación versionada de créditos nuevos; no reconstruye pagos históricos."""
from decimal import Decimal
from sqlalchemy import text
from creddt_finance import decimal_finito, plan_imputacion_fija, imputar_pago_programado

SCHEMA_SQL = '''
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
'''


def cuotas(conn, loan):
    return conn.execute(text('''SELECT id_cuota,nro_cuota,valor_cuota,estado
       FROM cuotas WHERE prestamo_id=:id ORDER BY nro_cuota'''), {'id':loan}).mappings().all()


def crear_plan(conn, loan, capital, count, cuota):
    plan = plan_imputacion_fija(capital,count,cuota)
    rows = cuotas(conn,loan)
    if len(rows) != len(plan):
        raise ValueError('El calendario no coincide con las condiciones del crédito.')
    for row, item in zip(rows,plan):
        conn.execute(text('''INSERT INTO creddt_private.installment_ledger
          (id_cuota,prestamo_id,version,capital_pendiente,interes_pendiente)
          VALUES(:q,:id,'flat_contract_v1',:c,:i)'''),
          dict(q=row['id_cuota'],id=loan,c=item['capital'],i=item['interes']))


def tiene_plan(conn, loan):
    return bool(conn.execute(text('SELECT 1 FROM creddt_private.installment_ledger WHERE prestamo_id=:id LIMIT 1'),{'id':loan}).scalar())


def aplicar(conn, loan, cuota_id, valor):
    # El llamador mantiene FOR UPDATE sobre el préstamo durante todo el pago.
    row=conn.execute(text('''SELECT capital_pendiente,interes_pendiente
       FROM creddt_private.installment_ledger WHERE prestamo_id=:id AND id_cuota=:q
       FOR UPDATE'''),dict(id=loan,q=cuota_id)).mappings().one()
    result=imputar_pago_programado(valor,row['capital_pendiente'],row['interes_pendiente'])
    conn.execute(text('''UPDATE creddt_private.installment_ledger
       SET capital_pendiente=:c,interes_pendiente=:i WHERE id_cuota=:q AND prestamo_id=:id'''),
       dict(c=result['capital_pendiente'],i=result['interes_pendiente'],q=cuota_id,id=loan))
    return result['interes_pagado'],result['capital_pagado']


def verificar(conn, loan, capital):
    rows=conn.execute(text('''SELECT q.id_cuota,q.estado,q.valor_cuota,l.capital_pendiente,l.interes_pendiente
       FROM cuotas q LEFT JOIN creddt_private.installment_ledger l ON l.id_cuota=q.id_cuota
       WHERE q.prestamo_id=:id'''),{'id':loan}).mappings().all()
    total=Decimal(0)
    for row in rows:
        if row['capital_pendiente'] is None:
            raise ValueError('Falta la distribución de una cuota; no se registró el pago.')
        pending=row['capital_pendiente']+row['interes_pendiente']
        expected=Decimal(0) if row['estado']=='Pagada' else decimal_finito(row['valor_cuota'])
        if pending != expected:
            raise ValueError('La cuota no concilia con su distribución; no se registró el pago.')
        total+=row['capital_pendiente']
    if total != decimal_finito(capital):
        raise ValueError('El capital pendiente no concilia; no se registró el pago.')


def plan_amortizado(capital,tasa,count):
    """Fórmula de abono vigente; última cuota ajustada sin centavos ocultos."""
    capital,tasa=map(decimal_finito,(capital,tasa))
    if capital<=0 or tasa<0 or count<=0:
        raise ValueError('Condiciones de abono inválidas.')
    n=int(count)
    factor=(1+tasa)**n
    quantum=Decimal('1') if capital==capital.to_integral_value() else Decimal('.01')
    cuota=(capital/n if tasa==0 else capital*tasa*factor/(factor-1)).quantize(quantum)
    if cuota<=0:
        raise ValueError('El saldo es demasiado pequeño para conservar este número de cuotas. Revisa la liquidación.')
    saldo=capital
    plan=[]
    for i in range(n):
        interes=(saldo*tasa).quantize(quantum)
        amortizacion=saldo if i==n-1 else min(saldo,cuota-interes)
        if amortizacion<0:
            raise ValueError('La cuota no cubre el interés del período.')
        total=amortizacion+interes
        plan.append(dict(capital=amortizacion,interes=interes,total=total))
        saldo-=amortizacion
    return cuota,plan


def recalcular_abono(conn,loan,capital,tasa):
    rows=[row for row in cuotas(conn,loan) if row['estado']!='Pagada']
    if any(row['estado']=='Parcial' for row in rows):
        raise ValueError('Completa la cuota parcialmente pagada antes de recalcular por abono a capital.')
    cuota,plan=plan_amortizado(capital,tasa,len(rows))
    for row,item in zip(rows,plan):
        conn.execute(text('''UPDATE creddt_private.installment_ledger SET
          capital_pendiente=:c,interes_pendiente=:i,version='amortized_after_prepayment_v1'
          WHERE id_cuota=:q AND prestamo_id=:id'''),dict(c=item['capital'],i=item['interes'],q=row['id_cuota'],id=loan))
        conn.execute(text('UPDATE cuotas SET valor_cuota=:v WHERE id_cuota=:q'),dict(v=item['total'],q=row['id_cuota']))
    return cuota
