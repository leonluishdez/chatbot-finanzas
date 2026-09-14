"""Reglas mensuales locales. Los vencimientos son estimaciones, no filas bancarias."""
import calendar
from contextlib import closing
import json
import os
import re
import sqlite3
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from finanzas import normalizar_texto, convertir_fecha, formatear_fecha


def ruta_datos():
    return Path(os.environ.get('RECURRENTES_DB', str(Path(__file__).resolve().parent / '.datos' / 'recurrentes.sqlite3')))


def leer_reglas(ruta=None):
    ruta = Path(ruta) if ruta is not None else ruta_datos()
    if not ruta.exists():
        return []
    with closing(sqlite3.connect(ruta.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        return [dict(json.loads(datos), id=identificador) for identificador, datos in
                db.execute('SELECT id, datos FROM reglas ORDER BY id')]


def validar_importe(valor):
    try:
        monto = Decimal(str(valor).replace('$', '').replace(',', '').strip())
        if not monto.is_finite() or monto <= 0 or monto > Decimal('999999999'):
            raise ValueError('El importe debe ser positivo y menor o igual a 999999999.')
        monto = monto.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        if monto <= 0:
            raise ValueError('El importe mínimo es 0.01.')
        return str(monto)
    except InvalidOperation as exc:
        raise ValueError('Importe no válido.') from exc


def validar_texto(valor):
    valor = valor.strip()
    if not valor or len(valor) > 120 or '\n' in valor:
        raise ValueError('Usa un texto de 1 a 120 caracteres, sin saltos de línea.')
    return valor


def guardar_accion(accion, partes, ruta=None, hoy=None):
    """Transacción atómica; una sola regla por cuenta y concepto/alias."""
    hoy = hoy or datetime.now()
    ruta = Path(ruta) if ruta is not None else ruta_datos()
    # Validar antes de crear almacenamiento.
    if accion == 'crear':
        if len(partes) != 6:
            raise ValueError('Formato: crear concepto | importe | día de pago | cuenta | subcategoría | dd/m/yy')
        concepto, importe, dia, cuenta, categoria, inicio = partes
        concepto, cuenta, categoria = map(validar_texto, (concepto, cuenta, categoria))
        importe = validar_importe(importe)
        if not dia.isdigit() or not 1 <= int(dia) <= 31:
            raise ValueError('El día de pago debe estar entre 1 y 31.')
        if '/' in inicio:
            inicio = convertir_fecha(inicio).strftime('%Y-%m')
        if not re.fullmatch(r'\d{4}-\d{2}', inicio):
            raise ValueError('Usa una fecha dd/m/yy del mes inicial.')
        try:
            fecha = datetime.strptime(inicio, '%Y-%m')
        except ValueError as exc:
            raise ValueError('Mes inicial no válido.') from exc
        if (fecha.year, fecha.month) < (hoy.year, hoy.month):
            raise ValueError('El inicio no puede ser anterior al mes actual.')
        regla = dict(concepto=concepto, importe=importe, dia=int(dia), cuenta=cuenta,
                     subcategoria=categoria, inicio=inicio, activa=True, alias=[])
    else:
        if accion not in ('pausar', 'activar', 'importe', 'alias'):
            raise ValueError('Acción no reconocida. Usa /recurrentes ayuda.')
        if len(partes) != (2 if accion in ('importe', 'alias') else 1):
            raise ValueError('Formato: pausar ID, activar ID, importe ID | monto, alias ID | descripción exacta')
        if not partes[0].isdigit() or int(partes[0]) < 1:
            raise ValueError('El ID debe ser un número positivo.')
        identificador = int(partes[0])
        if accion == 'importe':
            valor = validar_importe(partes[1])
        elif accion == 'alias':
            valor = validar_texto(partes[1])
        if not ruta.exists():
            raise ValueError('No existe ese recurrente.')
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(ruta)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS reglas (id INTEGER PRIMARY KEY, datos TEXT NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        reglas = [dict(json.loads(d), id=i) for i, d in db.execute('SELECT id, datos FROM reglas')]
        if accion != 'crear':
            regla = next((r for r in reglas if r['id'] == identificador), None)
            if regla is None:
                raise ValueError('No existe ese recurrente.')
            if accion in ('pausar', 'activar'):
                regla['activa'] = accion == 'activar'
            elif accion == 'importe':
                regla['importe'] = valor
            elif normalizar_texto(valor) not in nombres_regla(regla):
                regla['alias'].append(valor)
        for otra in reglas:
            if accion != 'crear' and otra['id'] == identificador:
                continue
            if normalizar_texto(otra['cuenta']) == normalizar_texto(regla['cuenta']) and nombres_regla(otra) & nombres_regla(regla):
                raise ValueError('Ya existe ese concepto o alias en esa cuenta. Modifica la regla existente.')
        if accion == 'crear':
            identificador = db.execute('INSERT INTO reglas(datos) VALUES (?)', (json.dumps(regla, ensure_ascii=False),)).lastrowid
        else:
            regla.pop('id', None)
            db.execute('UPDATE reglas SET datos=? WHERE id=?', (json.dumps(regla, ensure_ascii=False), identificador))
    return identificador


def nombres_regla(regla):
    return {normalizar_texto(n) for n in [regla['concepto'], *regla.get('alias', [])]}


def generar_vencimientos(reglas, movimientos, periodos, hoy=None):
    """Proyecta meses futuros. Un cargo real sustituye su estimación, incluso pagado.

    Coincidencia exacta normalizada de cuenta, concepto/alias y mes de pago.
    No exige igual importe: el cargo real puede variar. No usa similitud difusa.
    """
    hoy = hoy or datetime.now()
    existentes = set()
    for m in movimientos:
        if normalizar_texto(m.get('Tipo de Movimiento', '')) != 'gasto':
            continue
        if normalizar_texto(m.get('Status', '')) not in ('pendiente', 'pagado'):
            continue
        if normalizar_texto(m.get('Tipo de Pago', '')) == 'meses':
            continue
        try:
            fecha = convertir_fecha(m.get('Fecha de Pago', ''))
        except (ValueError, TypeError):
            continue
        concepto = m.get('Descripcion') or m.get('Concepto') or ''
        existentes.add((normalizar_texto(m.get('Cuenta', '')), normalizar_texto(concepto), fecha.year, fecha.month))
    resultados = []
    for regla in reglas:
        if not regla['activa']:
            continue
        for anio, mes in sorted({(p['anio'], p['mes']) for p in periodos if p.get('anio')}):
            if (anio, mes) <= (hoy.year, hoy.month) or f'{anio:04d}-{mes:02d}' < regla['inicio']:
                continue
            if any((normalizar_texto(regla['cuenta']), nombre, anio, mes) in existentes for nombre in nombres_regla(regla)):
                continue
            dia = min(regla['dia'], calendar.monthrange(anio, mes)[1])
            resultados.append({'Tipo de Movimiento': 'Gasto', 'Fecha de Pago': formatear_fecha(datetime(anio, mes, dia)),
                               'Monto de Compra': regla['importe'], 'Cuenta': regla['cuenta'],
                               'Descripcion': regla['concepto'], 'Subcategoria': regla['subcategoria'],
                               'Tipo de Pago': 'Contado', 'Status': 'Pendiente', '_recurrente_id': regla['id']})
    return resultados


AYUDA = '''Gastos recurrentes mensuales
/recurrentes — ver reglas
/recurrentes crear concepto | importe | día de pago | cuenta | subcategoría | dd/m/yy
/recurrentes pausar ID
/recurrentes activar ID
/recurrentes importe ID | nuevo importe
/recurrentes alias ID | descripción exacta del banco

Usa la cuenta y subcategoría como aparecen en Sheets. El día es el vencimiento, no la compra; el 31 se ajusta al último día del mes.
Las reglas se guardan en esta Mac. Se incluyen en las proyecciones de pendientes futuros y no crean filas en Sheets.
Un gasto registrado del mismo concepto (o alias), cuenta y mes sustituye la estimación. Si el banco usa otro nombre, añade su descripción como alias para evitar contar ambos.
Pausar o cambiar el importe afecta a todos los meses futuros estimados; no modifica cargos reales.'''


def procesar_comando(texto, ruta=None, hoy=None):
    comando = texto.split(maxsplit=1)
    contenido = comando[1].strip() if len(comando) > 1 else ''
    if contenido.lower() == 'ayuda':
        return AYUDA
    if not contenido or contenido.lower() == 'listar':
        reglas = leer_reglas(ruta)
        if not reglas:
            return 'No tienes gastos recurrentes.\n\n' + AYUDA
        return '\n\n'.join(f"{r['id']}. {r['concepto']} — ${Decimal(r['importe']):,.2f}\n"
                            f"{r['cuenta']} · día {r['dia']} · desde {formatear_fecha(datetime.strptime(r['inicio'], '%Y-%m'))} · "
                            f"{'Activo' if r['activa'] else 'Pausado'}" for r in reglas) + '\n\n/recurrentes ayuda'
    accion, _, resto = contenido.partition(' ')
    partes = [p.strip() for p in resto.split('|')]
    identificador = guardar_accion(accion.lower(), partes, ruta, hoy)
    return f'Recurrente {identificador}: cambio guardado. Consulta los pendientes de los próximos meses para ver la proyección.\n/recurrentes para ver tus reglas.'
