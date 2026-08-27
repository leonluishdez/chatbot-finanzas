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


def crear_teclado_categorias():

    teclado = []
    fila = []

    for categoria in CATEGORIAS:

        boton = InlineKeyboardButton(
            categoria,
            callback_data=(
                f"categoria:{categoria}"
            )
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

        # =========================
        # REGISTRAR
        # =========================

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

        # =========================
        # CONSULTAR
        # =========================

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

        if (
            mes is None
            and anio is None
            and subcategoria is None
            and cuenta is None
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
            cuenta=cuenta
        )

        filtros = []

        if subcategoria is not None:

            filtros.append(
                subcategoria
            )

        if cuenta is not None:

            filtros.append(
                cuenta
            )

        if mes is not None:

            filtros.append(
                f"mes {mes}"
            )

        if anio is not None:

            filtros.append(
                str(anio)
            )

        if filtros:

            detalle = " · ".join(
                filtros
            )

            respuesta = (
                f"Total ({detalle}): "
                f"${total:,.2f}"
            )

        else:

            respuesta = (
                f"Total: "
                f"${total:,.2f}"
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


async def manejar_categoria(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query is None:
        return

    # Telegram espera que respondamos
    # la callback del botón.
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
        categoria,
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
                f"Descripción: "
                f"{datos['concepto']}\n"
                f"Monto: "
                f"${datos['monto']:,.2f}\n"
                f"Cuenta: "
                f"{datos['cuenta']}\n"
                f"Categoría: "
                f"{categoria}\n"
                f"Tipo de pago: "
                f"{tipo_pago}\n"
                f"Plazos: "
                f"{plazos}\n"
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


async def manejar_error(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        f"Error de Telegram: "
        f"{context.error}"
    )


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

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            responder_mensaje
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            manejar_categoria,
            pattern=r"^categoria:"
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