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


# =============================
# CUENTAS
# =============================

CUENTA_INGRESOS = "BBVA Debito"

CUENTAS_GASTO = [
    "BBVA Platinum",
    "Citibanamex Oro",
    "Citibanamex Costco",
    "Invex",
]


# =============================
# CATEGORÍAS
# =============================

CATEGORIAS_GASTO = [
    "Comida",
    "Transporte",
    "Servicios",
    "Entretenimiento",
    "Viajes",
    "Salud",
    "Aprendizaje",
    "Varios",
]


CATEGORIAS_INGRESO = [
    "Comisiones",
    "Sueldo",
    "Bonos",
    "Freelance",
    "Otros ingresos",
]


# =============================
# FUNCIONES AUXILIARES
# =============================

def obtener_tipo_pago(
    tipo_movimiento,
    plazos
):

    if tipo_movimiento == "Ingreso":
        return "Contado"

    if plazos > 1:
        return "Meses"

    return "Contado"


def obtener_status_default(
    tipo_movimiento
):

    if tipo_movimiento == "Ingreso":
        return "Pagado"

    return "Pendiente"


def crear_teclado_categorias(
    tipo_movimiento="Gasto"
):

    if tipo_movimiento == "Ingreso":
        categorias = CATEGORIAS_INGRESO

    else:
        categorias = CATEGORIAS_GASTO

    teclado = []
    fila = []

    for categoria in categorias:

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


def crear_teclado_cuentas():

    teclado = []
    fila = []

    for cuenta in CUENTAS_GASTO:

        boton = InlineKeyboardButton(
            cuenta,
            callback_data=f"cuenta:{cuenta}"
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


def crear_resumen_confirmacion(
    datos
):

    tipo_movimiento = datos.get(
        "tipo_movimiento",
        "Gasto"
    )

    plazos = datos.get(
        "plazos",
        1
    )

    tipo_pago = obtener_tipo_pago(
        tipo_movimiento,
        plazos
    )

    status = obtener_status_default(
        tipo_movimiento
    )

    return (
        "Confirma el movimiento:\n\n"
        f"Tipo: {tipo_movimiento}\n"
        f"Descripción: {datos['concepto']}\n"
        f"Monto: ${datos['monto']:,.2f}\n"
        f"Cuenta: {datos['cuenta']}\n"
        f"Categoría: {datos['categoria']}\n"
        f"Tipo de pago: {tipo_pago}\n"
        f"Plazos: {plazos}\n"
        f"Status: {status}"
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

    # =============================
    # ESPERANDO DESCRIPCIÓN
    # =============================

    if context.user_data.get(
        "esperando_descripcion"
    ):

        movimiento_pendiente = context.user_data.get(
            "gasto_pendiente"
        )

        if movimiento_pendiente is None:

            context.user_data.pop(
                "esperando_descripcion",
                None
            )

            await update.message.reply_text(
                "El movimiento pendiente ya no existe."
            )

            return

        movimiento_pendiente[
            "concepto"
        ] = (
            mensaje_usuario
            .strip()
            .capitalize()
        )

        context.user_data[
            "gasto_pendiente"
        ] = movimiento_pendiente

        context.user_data.pop(
            "esperando_descripcion",
            None
        )

        tipo_movimiento = movimiento_pendiente.get(
            "tipo_movimiento",
            "Gasto"
        )

        # Ingreso:
        # siempre va a BBVA Débito.
        if tipo_movimiento == "Ingreso":

            movimiento_pendiente[
                "cuenta"
            ] = CUENTA_INGRESOS

            context.user_data[
                "gasto_pendiente"
            ] = movimiento_pendiente

        # Gasto:
        # si falta cuenta, preguntamos.
        elif movimiento_pendiente.get(
            "cuenta"
        ) is None:

            await update.message.reply_text(
                (
                    f"Descripción: "
                    f"{movimiento_pendiente['concepto']}\n\n"
                    "Selecciona la tarjeta que usaste:"
                ),
                reply_markup=(
                    crear_teclado_cuentas()
                )
            )

            return

        subcategoria = movimiento_pendiente.get(
            "subcategoria"
        )

        if subcategoria is not None:

            movimiento_pendiente[
                "categoria"
            ] = subcategoria

            context.user_data[
                "gasto_pendiente"
            ] = movimiento_pendiente

            await update.message.reply_text(
                crear_resumen_confirmacion(
                    movimiento_pendiente
                ),
                reply_markup=(
                    crear_teclado_confirmacion()
                )
            )

            return

        await update.message.reply_text(
            (
                f"Descripción: "
                f"{movimiento_pendiente['concepto']}\n\n"
                "Selecciona la categoría:"
            ),
            reply_markup=(
                crear_teclado_categorias(
                    tipo_movimiento
                )
            )
        )

        return

    # =============================
    # MENSAJE NORMAL
    # =============================

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

        print(
            datos
        )

        intencion = datos[
            "intencion"
        ]

        # =============================
        # REGISTRAR
        # =============================

        if intencion == "registrar":

            tipo_movimiento = datos.get(
                "tipo_movimiento",
                "Gasto"
            )

            monto = datos[
                "monto"
            ]

            cuenta = datos[
                "cuenta"
            ]

            concepto = datos[
                "concepto"
            ]

            subcategoria = datos.get(
                "subcategoria"
            )

            plazos = datos.get(
                "plazos",
                1
            )

            # =============================
            # INGRESOS
            # =============================

            if tipo_movimiento == "Ingreso":

                cuenta = CUENTA_INGRESOS

                # Un ingreso nunca debería
                # manejar MSI.
                plazos = 1

            # =============================
            # VALIDAR MONTO
            # =============================

            if monto is None:

                if tipo_movimiento == "Ingreso":

                    mensaje_error = (
                        "No encontré el monto del ingreso."
                    )

                else:

                    mensaje_error = (
                        "No encontré el monto del gasto."
                    )

                await update.message.reply_text(
                    mensaje_error
                )

                return

            # =============================
            # GUARDAR MOVIMIENTO TEMPORAL
            # =============================

            context.user_data[
                "gasto_pendiente"
            ] = {
                "tipo_movimiento": tipo_movimiento,
                "monto": monto,
                "cuenta": cuenta,
                "concepto": concepto,
                "subcategoria": subcategoria,
                "plazos": plazos,
            }

            # =============================
            # FALTA DESCRIPCIÓN
            # =============================

            if not concepto:

                context.user_data[
                    "esperando_descripcion"
                ] = True

                if tipo_movimiento == "Ingreso":

                    pregunta = (
                        "¿De qué fue el ingreso?"
                    )

                else:

                    pregunta = (
                        "¿Qué compraste?"
                    )

                await update.message.reply_text(
                    pregunta
                )

                return

            # =============================
            # FALTA CUENTA EN GASTO
            # =============================

            if (
                tipo_movimiento == "Gasto"
                and cuenta is None
            ):

                await update.message.reply_text(
                    (
                        "Selecciona la tarjeta "
                        "que usaste:"
                    ),
                    reply_markup=(
                        crear_teclado_cuentas()
                    )
                )

                return

            # =============================
            # SUBCATEGORÍA YA DETECTADA
            # =============================

            if subcategoria is not None:

                movimiento_pendiente = (
                    context.user_data[
                        "gasto_pendiente"
                    ]
                )

                movimiento_pendiente[
                    "categoria"
                ] = subcategoria

                context.user_data[
                    "gasto_pendiente"
                ] = movimiento_pendiente

                await update.message.reply_text(
                    crear_resumen_confirmacion(
                        movimiento_pendiente
                    ),
                    reply_markup=(
                        crear_teclado_confirmacion()
                    )
                )

                return

            # =============================
            # PEDIR CATEGORÍA
            # =============================

            tipo_pago = obtener_tipo_pago(
                tipo_movimiento,
                plazos
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
                f"Tipo: {tipo_movimiento}\n"
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
                    crear_teclado_categorias(
                        tipo_movimiento
                    )
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

        tipo_movimiento = datos.get(
            "tipo_movimiento",
            "Gasto"
        )

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
            status=status,
            tipo_movimiento=tipo_movimiento
        )

        # =============================
        # RESPUESTA NATURAL
        # =============================

        partes = []

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

        detalle = " ".join(
            partes
        )

        # =============================
        # TOTAL = 0
        # =============================

        if total == 0:

            if tipo_movimiento == "Ingreso":

                inicio = (
                    "No encontré ingresos"
                )

            else:

                inicio = (
                    "No tienes gastos"
                )

            if status is not None:

                inicio += (
                    f" {status.lower()}"
                )

            if detalle:

                respuesta = (
                    f"{inicio} {detalle}."
                )

            else:

                respuesta = (
                    f"{inicio}."
                )

        # =============================
        # TOTAL > 0
        # =============================

        else:

            if tipo_movimiento == "Ingreso":

                inicio = (
                    f"Total de ingresos: "
                    f"${total:,.2f}"
                )

            elif status == "Pendiente":

                inicio = (
                    f"Tienes ${total:,.2f} pendiente"
                )

            elif status == "Pagado":

                inicio = (
                    f"Tienes ${total:,.2f} pagado"
                )

            else:

                inicio = (
                    f"Total de gastos: "
                    f"${total:,.2f}"
                )

            if detalle:

                respuesta = (
                    f"{inicio} {detalle}."
                )

            else:

                respuesta = (
                    f"{inicio}."
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
# SELECCIÓN DE CUENTA
# =============================

async def manejar_cuenta(
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
            "El movimiento pendiente ya no existe."
        )

        return

    tipo_movimiento = datos.get(
        "tipo_movimiento",
        "Gasto"
    )

    # Por seguridad:
    # un ingreso siempre va a BBVA Débito.
    if tipo_movimiento == "Ingreso":

        cuenta = CUENTA_INGRESOS

    else:

        cuenta = query.data.replace(
            "cuenta:",
            "",
            1
        )

        # Solo permitimos las tarjetas actuales.
        if cuenta not in CUENTAS_GASTO:

            await query.edit_message_text(
                "La cuenta seleccionada no es válida."
            )

            return

    datos[
        "cuenta"
    ] = cuenta

    context.user_data[
        "gasto_pendiente"
    ] = datos

    subcategoria = datos.get(
        "subcategoria"
    )

    if subcategoria is not None:

        datos[
            "categoria"
        ] = subcategoria

        context.user_data[
            "gasto_pendiente"
        ] = datos

        await query.edit_message_text(
            crear_resumen_confirmacion(
                datos
            ),
            reply_markup=(
                crear_teclado_confirmacion()
            )
        )

        return

    await query.edit_message_text(
        (
            f"Cuenta: {cuenta}\n\n"
            "Ahora selecciona la categoría:"
        ),
        reply_markup=(
            crear_teclado_categorias(
                tipo_movimiento
            )
        )
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
            "El movimiento pendiente ya no existe."
        )

        return

    categoria = query.data.replace(
        "categoria:",
        "",
        1
    )

    datos[
        "categoria"
    ] = categoria

    context.user_data[
        "gasto_pendiente"
    ] = datos

    await query.edit_message_text(
        crear_resumen_confirmacion(
            datos
        ),
        reply_markup=(
            crear_teclado_confirmacion()
        )
    )


# =============================
# CONFIRMAR MOVIMIENTO
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
            "No hay ningún movimiento pendiente."
        )

        return

    tipo_movimiento = datos.get(
        "tipo_movimiento",
        "Gasto"
    )

    # Reglas finales de cuenta.
    if tipo_movimiento == "Ingreso":

        datos[
            "cuenta"
        ] = CUENTA_INGRESOS

    elif datos.get(
        "cuenta"
    ) not in CUENTAS_GASTO:

        await query.edit_message_text(
            "La cuenta del gasto no es válida."
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

    if tipo_movimiento == "Ingreso":
        plazos = 1

    tipo_pago = obtener_tipo_pago(
        tipo_movimiento,
        plazos
    )

    status = obtener_status_default(
        tipo_movimiento
    )

    fila = [
        tipo_movimiento,
        fecha_actual,
        datos["monto"],
        datos["cuenta"],
        "",
        datos["concepto"],
        datos["categoria"],
        tipo_pago,
        plazos,
        status,
    ]

    try:

        registrar_movimiento(
            fila
        )

        context.user_data.pop(
            "gasto_pendiente",
            None
        )

        context.user_data.pop(
            "esperando_descripcion",
            None
        )

        await query.edit_message_text(
            (
                "Movimiento registrado ✅\n\n"
                f"Tipo: {tipo_movimiento}\n"
                f"Descripción: {datos['concepto']}\n"
                f"Monto: ${datos['monto']:,.2f}\n"
                f"Cuenta: {datos['cuenta']}\n"
                f"Categoría: {datos['categoria']}\n"
                f"Tipo de pago: {tipo_pago}\n"
                f"Plazos: {plazos}\n"
                f"Status: {status}"
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
# CANCELAR MOVIMIENTO
# =============================

async def cancelar_gasto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query is None:
        return

    await query.answer()

    context.user_data.pop(
        "gasto_pendiente",
        None
    )

    context.user_data.pop(
        "esperando_descripcion",
        None
    )

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

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            responder_mensaje
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            manejar_cuenta,
            pattern=r"^cuenta:"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            manejar_categoria,
            pattern=r"^categoria:"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            confirmar_gasto,
            pattern=r"^confirmar_gasto$"
        )
    )

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