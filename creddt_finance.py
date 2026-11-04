"""Simulación reproducible del crédito Normal. Conserva la fórmula vigente."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN

CENT = Decimal('0.01')

def decimal_finito(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Escribe un valor numérico válido.') from None
    if not amount.is_finite():
        raise ValueError('El valor debe ser finito.')
    return amount

def tasa_normal_default(cuotas):
    return Decimal('0.0433') if int(cuotas) == 15 else Decimal('0.0427')

def cotizar_normal(monto, cuotas, frecuencia='Mensual', tasa_mensual=None, permitir_cero=False):
    capital = decimal_finito(monto).quantize(CENT)
    if isinstance(cuotas, bool) or decimal_finito(cuotas) != int(cuotas) or int(cuotas) not in (12, 15):
        raise ValueError('El crédito Normal conserva las opciones de 12 o 15 cuotas.')
    cuotas = int(cuotas)
    if capital <= 0:
        raise ValueError('El capital debe ser mayor a cero.')
    frecuencia = str(frecuencia).strip().title()
    if frecuencia not in ('Mensual', 'Quincenal'):
        raise ValueError('Selecciona frecuencia mensual o quincenal.')
    tasa = tasa_normal_default(cuotas) if tasa_mensual is None else decimal_finito(tasa_mensual)
    if tasa < 0 or tasa > 1 or (tasa == 0 and not permitir_cero):
        raise ValueError('La tasa debe ser mayor a 0 y hasta 100 %. La tasa cero requiere autorización de configuración.')
    tasa = tasa.quantize(Decimal('0.000001'))
    if tasa == 0 and not permitir_cero:
        raise ValueError('La tasa es demasiado pequeña para la precisión admitida.')
    # Regla heredada expresamente conservada: capital/n + capital*tasa;
    # en quincenal se divide esa cuota entre dos. No cambia el número de pagos.
    base = capital / cuotas + capital * tasa
    if frecuencia == 'Quincenal':
        base /= 2
    cuota = ((base / 1000).quantize(Decimal('1'), rounding=ROUND_HALF_EVEN) * 1000).quantize(CENT)
    if cuota <= 0:
        raise ValueError('El capital es demasiado pequeño para el redondeo vigente de la cuota.')
    total = cuota * cuotas
    return dict(capital=capital, cuotas=cuotas, frecuencia=frecuencia,
                tasa_mensual=tasa, cuota=cuota, total=total,
                diferencia_total_capital=total-capital,
                interes_referencia_mensual=(capital*tasa).quantize(CENT),
                version='normal_legacy_decimal_v1')

def calendario_normal(cotizacion, fecha_inicio):
    days = 15 if cotizacion['frecuencia'] == 'Quincenal' else 30
    return [{'Cuota': i, 'Vencimiento': fecha_inicio + timedelta(days=days*i),
             'Valor (COP)': cotizacion['cuota']}
            for i in range(1, cotizacion['cuotas']+1)]

def distribuir_cuota(valor, saldo, tasa, interes_periodo=None, interes_ya_pagado=0):
    """Imputa un pago sin volver a causar interés al fraccionar una misma cuota."""
    valor, saldo, tasa = map(decimal_finito, (valor, saldo, tasa))
    interes_periodo = (saldo*tasa).quantize(CENT) if interes_periodo is None else decimal_finito(interes_periodo)
    pendiente = max(Decimal(0), interes_periodo-decimal_finito(interes_ya_pagado))
    interes = min(valor, pendiente)
    capital = min(saldo, valor-interes)
    return interes.quantize(CENT), capital.quantize(CENT), (saldo-capital).quantize(CENT), interes_periodo


def plan_imputacion_fija(capital, cantidad, cuota):
    """Descompone el calendario pactado sin inflar capital ni dinero recibido.

    Para la fórmula vigente sobre capital inicial, el interés contractual total
    es la diferencia entre el total de cuotas y el principal. Los ajustes se
    distribuyen en el calendario, sin agregar cargos a la última cuota.
    No modifica ni reconstruye préstamos históricos.
    """
    capital, cuota = (decimal_finito(x).quantize(CENT) for x in (capital, cuota))
    n = decimal_finito(cantidad)
    if n != int(n) or n <= 0 or capital <= 0 or cuota <= 0:
        raise ValueError('Capital, cuota y cantidad deben ser positivos; la cantidad debe ser entera.')
    n = int(n)
    if cuota * n < capital:
        raise ValueError('Las cuotas programadas no cubren el capital. Revisa el plazo y la frecuencia antes de crear el crédito.')
    # Diferencias de acumulados redondeados conservan exactamente el principal.
    # Capital entero: imputaciones al peso, coherentes con el cobro en COP.
    rows = []
    previo = Decimal(0)
    quantum = Decimal('1') if capital == capital.to_integral_value() else CENT
    for numero in range(1, n + 1):
        acumulado = (capital * numero / n).quantize(quantum)
        amortizacion = acumulado - previo
        interes = cuota - amortizacion
        if interes < 0:
            raise ValueError('La precisión de la cuota no permite distribuir el capital.')
        rows.append(dict(numero=numero, capital=amortizacion, interes=interes, total=cuota))
        previo = acumulado
    return rows


def imputar_pago_programado(valor, capital_pendiente, interes_pendiente):
    """Consume saldos de UNA cuota; los saldos deben persistir en la transacción."""
    valor, capital, interes = (decimal_finito(x).quantize(CENT) for x in
                               (valor, capital_pendiente, interes_pendiente))
    if valor <= 0 or capital < 0 or interes < 0:
        raise ValueError('El pago debe ser positivo y los saldos no negativos.')
    if valor > capital + interes:
        raise ValueError('El pago supera el saldo de esta cuota.')
    pagado_interes = min(valor, interes)
    pagado_capital = valor - pagado_interes
    return dict(capital_pagado=pagado_capital, interes_pagado=pagado_interes,
                capital_pendiente=capital-pagado_capital,
                interes_pendiente=interes-pagado_interes)
