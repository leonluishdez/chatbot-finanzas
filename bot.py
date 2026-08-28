import os
from datetime import datetime

from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from sheets import (
    obtener_movimientos,
    registrar_movimiento
)

from finanzas import (
    interpretar_mensaje,
    calcular_total
)


# =============================
# CONFIGURACIÓN
# =============================

load_dotenv()

TOKEN = os.getenv(
    "TELEGRAM_TOKEN"
)


CATEGORIAS = [
    "Comida",
    "Transporte",
    "Servicios",
    "Entretenimiento",
    "Viajes",
    "Salud",
    "Aprendizaje",
    "Varios",
]


# =============================
# TECLADOS
# =============================

def crear_teclado_categorias():

    teclado = []
    fila = []

    for categoria in CATEGORIAS:

        boton = InlineKeyboardButton(
            categoria,
            callback_data=f"categoria:{categoria}"
        )

        fila.append(
            boton
        )

        if len(fila) == 2:

            teclado.append(
                fila
            )

            fila = []

    if fila:
        teclado.append(
            fila
        )

    return InlineKeyboardMarkup(
        teclado
    )


def crear_teclado_confirmacion():

    teclado = [
        [
            InlineKeyboardButton(
                "Confirmar ✅",
                callback_data="confirmar_gasto"
            ),
            InlineKeyboardButton(
                "Cancelar ❌",
                callback_data="cancelar_gasto"
            )
        ]
    ]

    return InlineKeyboardMarkup(
        teclado
    )


# =============================
# MENSAJES DE TEXTO
# =============================

async def responder_mensaje(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.message is None:
        return

    mensaje_usuario = (
        update.message.text
        .strip()
    )

    print(
        f"Mensaje recibido: "
        f"{mensaje_usuario}"
    )

    try:

        movimientos = (
            obtener_movimientos()
        )

        datos = interpretar_mensaje(
            mensaje_usuario,
            movimientos
        )

        print(datos)

        intencion = datos[
            "intencion"
        ]

        # =============================
        # REGISTRAR
        # =============================

        if intencion == "registrar":

            monto = datos[
                "monto"
            ]

            cuenta = datos[
                "cuenta"
            ]

            concepto = datos[
                "concepto"
            ]

            plazos = datos.get(
                "plazos",
                1
            )

            if monto is None:

                await update.message.reply_text(
                    "No encontré el monto del gasto."
                )

                return

            if cuenta is None:

                await update.message.reply_text(
                    "No pude identificar la cuenta."
                )

                return

            if not concepto:

                await update.message.reply_text(
                    "No pude identificar la descripción del gasto."
                )

                return

            context.user_data[
                "gasto_pendiente"
            ] = {
                "monto": monto,
                "cuenta": cuenta,
                "concepto": concepto,
                "plazos": plazos,
            }

            tipo_pago = (
                "Meses"
                if plazos > 1
                else "Contado"
            )

            if plazos > 1:

                detalle_pago = (
                    f"{plazos} meses"
                )

            else:

                detalle_pago = (
                    "Contado"
                )

            respuesta = (
                "Voy a registrar:\n\n"
                f"Descripción: {concepto}\n"
                f"Monto: ${monto:,.2f}\n"
                f"Cuenta: {cuenta}\n"
                f"Tipo de pago: {tipo_pago}\n"
                f"Plazos: {detalle_pago}\n\n"
                "Selecciona la categoría:"
            )

            await update.message.reply_text(
                respuesta,
                reply_markup=(
                    crear_teclado_categorias()
                )
            )

            return

        # =============================
        # CONSULTAR
        # =============================

        mes = datos[
            "mes"
        ]

        anio = datos[
            "anio"
        ]

        subcategoria = datos[
            "subcategoria"
        ]

        cuenta = datos[
            "cuenta"
        ]

        status = datos[
            "status"
        ]

        if (
            mes is None
            and anio is None
            and subcategoria is None
            and cuenta is None
            and status is None
        ):

            await update.message.reply_text(
                "No pude identificar qué quieres consultar."
            )

            return

        total = calcular_total(
            movimientos,
            mes=mes,
            anio=anio,
            subcategoria=subcategoria,
            cuenta=cuenta,
            status=status
        )

        if total == 0:

            partes = []

            if subcategoria is not None:
                partes.append(
                    f"de {subcategoria}"
                )

            if cuenta is not None:
                partes.append(
                    f"con {cuenta}"
                )

            if status is not None:
                partes.append(
                    status.lower()
                )

            if mes is not None:
                partes.append(
                    "este mes"
                    if (
                        mes == datetime.now().month
                        and anio == datetime.now().year
                    )
                    else f"en {mes}/{anio}"
                )

            detalle = " ".join(
                partes
            )

            respuesta = (
                f"No tienes gastos {detalle}."
            )

        else:

            partes = []

            if status is not None:

                if status == "Pendiente":
                    inicio = (
                        f"Tienes ${total:,.2f} pendiente"
                    )

                elif status == "Pagado":
                    inicio = (
                        f"Tienes ${total:,.2f} pagado"
                    )

                else:
                    inicio = (
                        f"Total: ${total:,.2f}"
                    )

            else:

                inicio = (
                    f"Total: ${total:,.2f}"
                )

            if subcategoria is not None:
                partes.append(
                    f"en {subcategoria}"
                )

            if cuenta is not None:
                partes.append(
                    f"con {cuenta}"
                )

            if mes is not None:

                if (
                    mes == datetime.now().month
                    and anio == datetime.now().year
                ):

                    partes.append(
                        "este mes"
                    )

                else:

                    partes.append(
                        f"en {mes}/{anio}"
                    )

            if partes:

                respuesta = (
                    inicio
                    + " "
                    + " ".join(partes)
                    + "."
                )

            else:

                respuesta = (
                    inicio + "."
                )

        await update.message.reply_text(
            respuesta
        )

    except Exception as error:

        print(
            f"Error procesando mensaje: "
            f"{error}"
        )

        await update.message.reply_text(
            "Ocurrió un error al procesar tu mensaje."
        )


# =============================
# SELECCIÓN DE CATEGORÍA
# =============================

async def manejar_categoria(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query is None:
        return

    await query.answer()

    datos = context.user_data.get(
        "gasto_pendiente"
    )

    if datos is None:

        await query.edit_message_text(
            "El gasto pendiente ya no existe."
        )

        return

    categoria = query.data.replace(
        "categoria:",
        "",
        1
    )

    datos["categoria"] = categoria

    context.user_data[
        "gasto_pendiente"
    ] = datos

    plazos = datos.get(
        "plazos",
        1
    )

    tipo_pago = (
        "Meses"
        if plazos > 1
        else "Contado"
    )

    await query.edit_message_text(
        (
            "Confirma el movimiento:\n\n"
            f"Descripción: {datos['concepto']}\n"
            f"Monto: ${datos['monto']:,.2f}\n"
            f"Cuenta: {datos['cuenta']}\n"
            f"Categoría: {categoria}\n"
            f"Tipo de pago: {tipo_pago}\n"
            f"Plazos: {plazos}"
        ),
        reply_markup=(
            crear_teclado_confirmacion()
        )
    )


# =============================
# CONFIRMAR GASTO
# =============================

async def confirmar_gasto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query is None:
        return

    await query.answer()

    datos = context.user_data.get(
        "gasto_pendiente"
    )

    if datos is None:

        await query.edit_message_text(
            "No hay ningún gasto pendiente."
        )

        return

    ahora = datetime.now()

    fecha_actual = (
        f"{ahora.day}/"
        f"{ahora.month}/"
        f"{ahora.year}"
    )

    plazos = datos.get(
        "plazos",
        1
    )

    tipo_pago = (
        "Meses"
        if plazos > 1
        else "Contado"
    )

    fila = [
        "Gasto",
        fecha_actual,
        datos["monto"],
        datos["cuenta"],
        "",
        datos["concepto"],
        datos["categoria"],
        tipo_pago,
        plazos,
        "Pendiente",
    ]

    try:

        registrar_movimiento(
            fila
        )

        context.user_data.pop(
            "gasto_pendiente",
            None
        )

        await query.edit_message_text(
            (
                "Movimiento registrado ✅\n\n"
                f"Descripción: {datos['concepto']}\n"
                f"Monto: ${datos['monto']:,.2f}\n"
                f"Cuenta: {datos['cuenta']}\n"
                f"Categoría: {datos['categoria']}\n"
                f"Tipo de pago: {tipo_pago}\n"
                f"Plazos: {plazos}\n"
                f"Status: Pendiente"
            )
        )

    except Exception as error:

        print(
            f"Error registrando movimiento: "
            f"{error}"
        )

        await query.edit_message_text(
            "No pude registrar el movimiento."
        )


# =============================
# CANCELAR GASTO
# =============================

async def cancelar_gasto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query is None:
        return

    await query.answer()

    datos = context.user_data.pop(
        "gasto_pendiente",
        None
    )

    if datos is None:

        await query.edit_message_text(
            "No había ningún movimiento pendiente."
        )

        return

    await query.edit_message_text(
        "Movimiento cancelado ❌"
    )


# =============================
# ERRORES
# =============================

async def manejar_error(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        f"Error de Telegram: "
        f"{context.error}"
    )


# =============================
# MAIN
# =============================

def main():

    if not TOKEN:

        raise RuntimeError(
            "No se encontró TELEGRAM_TOKEN."
        )

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )

    # Mensajes normales
    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            responder_mensaje
        )
    )

    # Selección de categoría
    app.add_handler(
        CallbackQueryHandler(
            manejar_categoria,
            pattern=r"^categoria:"
        )
    )

    # Confirmar registro
    app.add_handler(
        CallbackQueryHandler(
            confirmar_gasto,
            pattern=r"^confirmar_gasto$"
        )
    )

    # Cancelar registro
    app.add_handler(
        CallbackQueryHandler(
            cancelar_gasto,
            pattern=r"^cancelar_gasto$"
        )
    )

    app.add_error_handler(
        manejar_error
    )

    print(
        "Bot iniciado..."
    )

    app.run_polling()


if __name__ == "__main__":
    main()