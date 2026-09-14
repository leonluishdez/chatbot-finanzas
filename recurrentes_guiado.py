"""Registro conversacional de reglas mensuales; no registra cargos en Sheets."""
import re
from datetime import datetime
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from finanzas import MESES, normalizar_texto, convertir_fecha, formatear_fecha
from recurrentes import guardar_accion, validar_importe, validar_texto

CLAVE = 'recurrente_pendiente'
EJEMPLO = 'Escribe, por ejemplo: Registra un gasto recurrente de Totalplay por $460 al mes.'


def interpretar_registro(texto):
    """None significa que el mensaje pertenece al flujo habitual."""
    normal = normalizar_texto(texto)
    if not re.match(r'^(?:registra|registrar|registra[r]?me)\b', normal) or not re.search(r'\brecurrente\b', normal):
        return None
    patron = r'^(?:registra|registrar|registrame)\s+(?:un\s+)?gasto\s+recurrente\s+(?:de\s+)?(.+?)\s+por\s+\$?([\d,]+(?:\.\d{1,2})?)\s*(?:al\s+mes|mensual(?:mente)?)?[.!]?\s*$'
    match = re.match(patron, texto.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(EJEMPLO)
    return {'concepto': validar_texto(match[1]), 'importe': validar_importe(match[2])}


def teclado(estado, opciones):
    filas = [[InlineKeyboardButton(label, callback_data=f"rec:{estado['token']}:{accion}")] for label, accion in opciones]
    filas.append([InlineKeyboardButton('Cancelar', callback_data=f"rec:{estado['token']}:cancelar")])
    return InlineKeyboardMarkup(filas)


def pedir(estado, cuentas, categorias):
    etapa = estado['etapa']
    if etapa == 'cuenta':
        return '¿Con qué cuenta pagarás este gasto mensual?', teclado(estado, [(c, f'cuenta:{i}') for i,c in enumerate(cuentas)])
    if etapa == 'categoria':
        return '¿Qué categoría tiene?', teclado(estado, [(c, f'categoria:{i}') for i,c in enumerate(categorias)])
    if etapa == 'dia':
        return '¿Qué día del mes vence? Escribe un número del 1 al 31. Es el día de pago, no el corte de la tarjeta.', teclado(estado, [])
    if etapa == 'inicio':
        return '¿Desde qué mes comienza? Escribe una fecha de ese mes en dd/m/yy (por ejemplo, 01/10/26) o el nombre del mes y año.', teclado(estado, [])
    return (f"Confirma el gasto recurrente:\n\n{estado['concepto']}\n"
            f"${float(estado['importe']):,.2f} mensuales\nCuenta: {estado['cuenta']}\n"
            f"Categoría: {estado['categoria']}\nDía de pago: {estado['dia']}\nDesde: {formatear_fecha(datetime.strptime(estado['inicio'], '%Y-%m'))} (mes inicial)\n\n"
            'Se guardará una regla para estimar los meses futuros; no se creará un cargo en Sheets.'), teclado(estado, [('Confirmar', 'confirmar')])


def interpretar_inicio(texto, hoy):
    texto = normalizar_texto(texto)
    if '/' in texto:
        fecha = convertir_fecha(texto)
    elif re.fullmatch(r'\d{4}-\d{2}', texto):
        try:
            fecha = datetime.strptime(texto, '%Y-%m')
        except ValueError as exc:
            raise ValueError('Mes no válido. Usa AAAA-MM.') from exc
    else:
        match = re.fullmatch(r'([a-z]+)(?:\s+(\d{4}))?', texto)
        if not match or match[1] not in MESES:
            raise ValueError('Escribe una fecha dd/m/yy o el mes y año, por ejemplo «octubre 2026».')
        anio = int(match[2]) if match[2] else hoy.year + (MESES[match[1]] < hoy.month)
        try:
            fecha = datetime(anio, MESES[match[1]], 1)
        except ValueError as exc:
            raise ValueError('Año no válido.') from exc
    if (fecha.year, fecha.month) < (hoy.year, hoy.month):
        raise ValueError('El mes inicial no puede estar en el pasado.')
    return fecha.strftime('%Y-%m')


async def manejar_texto_recurrente(update, context, cuentas, categorias, hoy=None):
    hoy = hoy or datetime.now()
    texto = update.message.text.strip()
    estado = context.user_data.get(CLAVE)
    if estado and normalizar_texto(texto) in ('cancelar', '/cancelar'):
        context.user_data.pop(CLAVE, None)
        await update.message.reply_text('Registro recurrente cancelado. No se guardó la regla.')
        return True
    if estado:
        try:
            if estado['etapa'] == 'dia':
                match = re.fullmatch(r'(?:el\s+)?(\d{1,2})', texto.lower())
                if not match or not 1 <= int(match[1]) <= 31:
                    raise ValueError('Escribe un día entre 1 y 31, o «cancelar».')
                estado['dia'] = int(match[1])
                estado['etapa'] = 'inicio'
            elif estado['etapa'] == 'inicio':
                estado['inicio'] = interpretar_inicio(texto, hoy)
                estado['etapa'] = 'confirmar'
            else:
                await update.message.reply_text('Usa los botones del registro recurrente o escribe «cancelar».')
                return True
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return True
    else:
        try:
            datos = interpretar_registro(texto)
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return True
        if datos is None:
            return False
        if context.user_data.get('gasto_pendiente'):
            await update.message.reply_text('Termina o cancela el gasto anterior antes de crear un recurrente.')
            return True
        estado = dict(datos, token=uuid4().hex[:12], etapa='cuenta')
        context.user_data[CLAVE] = estado
    mensaje, botones = pedir(estado, cuentas, categorias)
    await update.message.reply_text(mensaje, reply_markup=botones)
    return True


async def manejar_boton_recurrente(update, context, cuentas, categorias):
    query = update.callback_query
    await query.answer()
    partes = (query.data or '').split(':')
    estado = context.user_data.get(CLAVE)
    if len(partes) < 3 or not estado or partes[1] != estado['token']:
        await query.edit_message_text('Este registro ya terminó o caducó. Inicia uno nuevo si lo necesitas.')
        return
    accion = partes[2]
    if accion == 'cancelar':
        context.user_data.pop(CLAVE, None)
        await query.edit_message_text('Registro recurrente cancelado. No se guardó la regla.')
        return
    if accion in ('cuenta', 'categoria') and estado['etapa'] == accion and len(partes) == 4:
        opciones = cuentas if accion == 'cuenta' else categorias
        if not partes[3].isdigit() or not 0 <= int(partes[3]) < len(opciones):
            return
        estado[accion] = opciones[int(partes[3])]
        estado['etapa'] = 'categoria' if accion == 'cuenta' else 'dia'
    elif accion == 'confirmar' and estado['etapa'] == 'confirmar':
        try:
            identificador = guardar_accion('crear', [estado['concepto'], estado['importe'], str(estado['dia']),
                                                    estado['cuenta'], estado['categoria'], estado['inicio']])
        except ValueError as exc:
            await query.edit_message_text(str(exc) + '\nCancela este registro para empezar de nuevo.', reply_markup=teclado(estado, []))
            return
        except Exception:
            await query.edit_message_text('No pude confirmar el guardado. Consulta /recurrentes antes de reintentar.', reply_markup=teclado(estado, [('Reintentar', 'confirmar')]))
            return
        context.user_data.pop(CLAVE, None)
        await query.edit_message_text(f"Recurrente {identificador} guardado: {estado['concepto']}.\n"
                                      'Ya se incluirá en tus proyecciones de pendientes futuros.\n/recurrentes para ver o modificar la regla.')
        return
    else:
        return
    mensaje, botones = pedir(estado, cuentas, categorias)
    await query.edit_message_text(mensaje, reply_markup=botones)
