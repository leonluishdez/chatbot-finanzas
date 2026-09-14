"""Avisos locales para gastos pendientes con fecha de pago próxima."""

import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from finanzas import convertir_fecha, convertir_monto, formatear_fecha, normalizar_texto


ZONA_HORARIA = ZoneInfo("America/Mexico_City")
HORA_RECORDATORIO = time(9, 0, tzinfo=ZONA_HORARIA)


def ruta_datos():
    return Path(
        os.environ.get(
            "RECORDATORIOS_DB",
            str(Path(__file__).resolve().parent / ".datos" / "recordatorios.sqlite3"),
        )
    )


def inicializar(ruta=None):
    ruta = Path(ruta) if ruta is not None else ruta_datos()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(ruta)) as db, db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS suscripciones "
            "(chat_id INTEGER PRIMARY KEY, activa INTEGER NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS envios "
            "(chat_id INTEGER NOT NULL, clave TEXT NOT NULL, "
            "PRIMARY KEY(chat_id, clave))"
        )
    return ruta


def activar(chat_id, ruta=None):
    ruta = inicializar(ruta)
    with closing(sqlite3.connect(ruta)) as db, db:
        db.execute(
            "INSERT INTO suscripciones(chat_id, activa) VALUES (?, 1) "
            "ON CONFLICT(chat_id) DO UPDATE SET activa=1",
            (int(chat_id),),
        )


def desactivar(chat_id, ruta=None):
    ruta = inicializar(ruta)
    with closing(sqlite3.connect(ruta)) as db, db:
        db.execute(
            "INSERT INTO suscripciones(chat_id, activa) VALUES (?, 0) "
            "ON CONFLICT(chat_id) DO UPDATE SET activa=0",
            (int(chat_id),),
        )


def chats_activos(ruta=None):
    ruta = ruta_datos() if ruta is None else Path(ruta)
    if not ruta.exists():
        return []
    with closing(sqlite3.connect(ruta.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        return [fila[0] for fila in db.execute("SELECT chat_id FROM suscripciones WHERE activa=1")]


def ya_enviado(chat_id, clave, ruta=None):
    ruta = ruta_datos() if ruta is None else Path(ruta)
    if not ruta.exists():
        return False
    with closing(sqlite3.connect(ruta.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        return db.execute(
            "SELECT 1 FROM envios WHERE chat_id=? AND clave=?",
            (int(chat_id), clave),
        ).fetchone() is not None


def marcar_enviado(chat_id, clave, ruta=None):
    ruta = inicializar(ruta)
    with closing(sqlite3.connect(ruta)) as db, db:
        db.execute(
            "INSERT OR IGNORE INTO envios(chat_id, clave) VALUES (?, ?)",
            (int(chat_id), clave),
        )


def vencimientos_pendientes(movimientos, fecha):
    """Devuelve solo gastos Pendiente de un día, sin modificar Sheets."""
    resultado = []
    for movimiento in movimientos:
        if normalizar_texto(movimiento.get("Tipo de Movimiento", "")) != "gasto":
            continue
        if normalizar_texto(movimiento.get("Status", "")) != "pendiente":
            continue
        try:
            fecha_pago = convertir_fecha(movimiento.get("Fecha de Pago", "")).date()
            monto = convertir_monto(movimiento.get("Monto de Compra", 0))
        except (TypeError, ValueError):
            continue
        if fecha_pago != fecha or monto <= 0:
            continue
        resultado.append(
            {
                "descripcion": str(
                    movimiento.get("Descripcion") or movimiento.get("Concepto") or "Sin descripción"
                ).strip(),
                "cuenta": str(movimiento.get("Cuenta", "")).strip(),
                "monto": monto,
            }
        )
    return sorted(resultado, key=lambda item: (item["cuenta"], item["descripcion"], item["monto"]))


def crear_mensaje(fecha, vencimientos):
    if not vencimientos:
        return None
    lineas = [
        "⏰ Recordatorio de pago",
        "",
        f"Mañana, {formatear_fecha(datetime.combine(fecha, time()))}, vence:",
        "",
    ]
    total = 0.0
    for item in vencimientos:
        lineas.append(f"• {item['descripcion']} — ${item['monto']:,.2f} ({item['cuenta']})")
        total += item["monto"]
    lineas.extend(["", f"Total: ${total:,.2f}"])
    return "\n".join(lineas)


async def enviar_recordatorios(context):
    """Trabajo diario: marca un aviso solo tras enviarlo correctamente."""
    hoy = datetime.now(ZONA_HORARIA).date()
    fecha = hoy + timedelta(days=1)
    movimientos = context.application.bot_data.get("obtener_movimientos")
    if movimientos is None:
        raise RuntimeError("No se configuró el origen de movimientos para recordatorios.")
    vencimientos = vencimientos_pendientes(movimientos(), fecha)
    mensaje = crear_mensaje(fecha, vencimientos)
    if mensaje is None:
        return
    clave = f"vencimiento:{fecha.isoformat()}"
    for chat_id in chats_activos():
        if ya_enviado(chat_id, clave):
            continue
        await context.bot.send_message(chat_id=chat_id, text=mensaje)
        marcar_enviado(chat_id, clave)


async def configurar_recordatorios(app):
    app.bot_data["obtener_movimientos"] = __import__("sheets").obtener_movimientos
    if app.job_queue is None:
        raise RuntimeError("La cola de recordatorios no está disponible.")
    app.job_queue.run_daily(enviar_recordatorios, time=HORA_RECORDATORIO, name="recordatorios-de-pago")
