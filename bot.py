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
    registrar_movimiento,
    registrar_movimientos
)

from finanzas import (
    interpretar_mensaje,
    calcular_total,
    generar_cuotas,
    calcular_fecha_corte,
    calcular_primera_fecha_pago,
    obtener_movimientos_filtrados,
    convertir_monto,
    convertir_fecha,
    normalizar_texto
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

CUENTA_INGRESOS = (
    "BBVA Debito"
)

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


# =============================
# TECLADO CATEGORÍAS
# =============================

def crear_teclado_categorias(
    tipo_movimiento="Gasto"
):

    if tipo_movimiento == "Ingreso":

        categorias = (
            CATEGORIAS_INGRESO
        )

    else:

        categorias = (
            CATEGORIAS_GASTO
        )

    teclado = []
    fila = []

    for categoria in categorias:

        boton = (
            InlineKeyboardButton(
                categoria,
                callback_data=(
                    f"categoria:"
                    f"{categoria}"
                )
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


# =============================
# TECLADO CUENTAS
# =============================

def crear_teclado_cuentas():

    teclado = []
    fila = []

    for cuenta in CUENTAS_GASTO:

        boton = (
            InlineKeyboardButton(
                cuenta,
                callback_data=(
                    f"cuenta:"
                    f"{cuenta}"
                )
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


# =============================
# TECLADO CONFIRMACIÓN
# =============================

def crear_teclado_confirmacion():

    teclado = [
        [
            InlineKeyboardButton(
                "Confirmar ✅",
                callback_data=(
                    "confirmar_gasto"
                )
            ),
            InlineKeyboardButton(
                "Cancelar ❌",
                callback_data=(
                    "cancelar_gasto"
                )
            )
        ]
    ]

    return InlineKeyboardMarkup(
        teclado
    )


# =============================
# RESUMEN DE CONFIRMACIÓN
# =============================

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

    resumen = (
        "Confirma el movimiento:\n\n"
        f"Tipo: {tipo_movimiento}\n"
        f"Descripción: "
        f"{datos['concepto']}\n"
        f"Monto: "
        f"${datos['monto']:,.2f}\n"
        f"Cuenta: "
        f"{datos['cuenta']}\n"
        f"Categoría: "
        f"{datos['categoria']}\n"
        f"Tipo de pago: "
        f"{tipo_pago}\n"
        f"Plazos: "
        f"{plazos}\n"
        f"Status: "
        f"{status}"
    )

    # =============================
    # INFORMACIÓN MSI
    # =============================

    if (
        tipo_movimiento == "Gasto"
        and plazos > 1
    ):

        fecha_compra = datos.get(
            "fecha_compra",
            datetime.now()
        )

        fecha_corte = (
            calcular_fecha_corte(
                fecha_compra,
                datos["cuenta"]
            )
        )

        primera_fecha_pago = (
            calcular_primera_fecha_pago(
                fecha_compra,
                datos["cuenta"]
            )
        )

        mensualidad = round(
            datos["monto"]
            / plazos,
            2
        )

        resumen += (
            "\n"
            f"Mensualidad aproximada: "
            f"${mensualidad:,.2f}"
        )

        if fecha_corte is not None:

            resumen += (
                "\n"
                f"Corte aplicable: "
                f"{fecha_corte.strftime('%d/%m/%Y')}"
            )

        if primera_fecha_pago is not None:

            resumen += (
                "\n"
                f"Primer pago: "
                f"{primera_fecha_pago.strftime('%d/%m/%Y')}"
            )

    return resumen

def crear_resumen_mensualidades(
    movimientos
):

    if not movimientos:
        return None

    movimientos_ordenados = sorted(
        movimientos,
        key=lambda movimiento: convertir_fecha(
            movimiento.get(
                "Fecha de Pago",
                ""
            )
        )
    )

    movimientos_por_cuenta = {}

    total_general = 0.0

    for movimiento in movimientos_ordenados:

        cuenta = str(
            movimiento.get(
                "Cuenta",
                "Sin cuenta"
            )
        ).strip()

        descripcion = str(
            movimiento.get(
                "Descripcion",
                "Sin descripción"
            )
        ).strip()

        try:

            monto = convertir_monto(
                movimiento.get(
                    "Monto de Compra",
                    0
                )
            )

        except (
            ValueError,
            TypeError
        ):

            monto = 0.0

        fecha = convertir_fecha(
            movimiento.get(
                "Fecha de Pago",
                ""
            )
        )

        if cuenta not in movimientos_por_cuenta:

            movimientos_por_cuenta[
                cuenta
            ] = []

        movimientos_por_cuenta[
            cuenta
        ].append(
            {
                "descripcion": descripcion,
                "monto": monto,
                "fecha": fecha,
            }
        )

        total_general += monto

    lineas = [
        "💳 Mensualidades pendientes",
        ""
    ]

    for cuenta, cargos in movimientos_por_cuenta.items():

        lineas.append(
            cuenta
        )

        subtotal = 0.0

        for cargo in cargos:

            lineas.append(
                (
                    f"• {cargo['descripcion']} "
                    f"— ${cargo['monto']:,.2f} "
                    f"({cargo['fecha'].strftime('%d/%m/%Y')})"
                )
            )

            subtotal += cargo[
                "monto"
            ]

        lineas.append(
            f"Subtotal: ${subtotal:,.2f}"
        )

        lineas.append(
            ""
        )

    lineas.append(
        f"Total: ${total_general:,.2f}"
    )

    return "\n".join(
        lineas
    )


# ============================================================
# MENSAJES DE TEXTO
# ============================================================

async def responder_mensaje(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.message is None:

        return

    mensaje_usuario = (
        update.message.text.strip()
    )

    # ========================================================
    # ESTAMOS ESPERANDO UNA DESCRIPCIÓN
    # ========================================================

    if context.user_data.get(
        "esperando_descripcion"
    ):

        movimiento_pendiente = (
            context.user_data.get(
                "gasto_pendiente"
            )
        )

        if movimiento_pendiente is None:

            context.user_data.pop(
                "esperando_descripcion",
                None
            )

            await update.message.reply_text(
                "El movimiento pendiente "
                "ya no existe."
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

        tipo_movimiento = (
            movimiento_pendiente.get(
                "tipo_movimiento",
                "Gasto"
            )
        )

        # -------------------------
        # INGRESO
        # -------------------------

        if tipo_movimiento == "Ingreso":

            movimiento_pendiente[
                "cuenta"
            ] = CUENTA_INGRESOS

            context.user_data[
                "gasto_pendiente"
            ] = movimiento_pendiente

        # -------------------------
        # GASTO SIN CUENTA
        # -------------------------

        elif movimiento_pendiente.get(
            "cuenta"
        ) is None:

            await update.message.reply_text(
                (
                    f"Descripción: "
                    f"{movimiento_pendiente['concepto']}"
                    "\n\n"
                    "Selecciona la tarjeta "
                    "que usaste:"
                ),
                reply_markup=(
                    crear_teclado_cuentas()
                )
            )

            return

        # -------------------------
        # SUBCATEGORÍA DETECTADA
        # -------------------------

        subcategoria = (
            movimiento_pendiente.get(
                "subcategoria"
            )
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

        # -------------------------
        # PEDIR CATEGORÍA
        # -------------------------

        await update.message.reply_text(
            (
                f"Descripción: "
                f"{movimiento_pendiente['concepto']}"
                "\n\n"
                "Selecciona la categoría:"
            ),
            reply_markup=(
                crear_teclado_categorias(
                    tipo_movimiento
                )
            )
        )

        return

    # ========================================================
    # MENSAJE NORMAL
    # ========================================================

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

        # ====================================================
        # REGISTRAR
        # ====================================================

        if intencion == "registrar":

            tipo_movimiento = datos.get(
                "tipo_movimiento",
                "Gasto"
            )

            monto = datos.get(
                "monto"
            )

            cuenta = datos.get(
                "cuenta"
            )

            concepto = datos.get(
                "concepto",
                ""
            )

            subcategoria = datos.get(
                "subcategoria"
            )

            plazos = datos.get(
                "plazos",
                1
            )

            fecha_compra = (
                datetime.now()
            )

            # -------------------------
            # INGRESOS
            # -------------------------

            if tipo_movimiento == "Ingreso":

                cuenta = CUENTA_INGRESOS

                plazos = 1

            # -------------------------
            # VALIDAR MONTO
            # -------------------------

            if monto is None:

                if tipo_movimiento == "Ingreso":

                    mensaje_error = (
                        "No encontré el monto "
                        "del ingreso."
                    )

                else:

                    mensaje_error = (
                        "No encontré el monto "
                        "del gasto."
                    )

                await update.message.reply_text(
                    mensaje_error
                )

                return

            # -------------------------
            # GUARDAR MOVIMIENTO
            # TEMPORAL
            # -------------------------

            context.user_data[
                "gasto_pendiente"
            ] = {
                "tipo_movimiento": tipo_movimiento,
                "monto": monto,
                "cuenta": cuenta,
                "concepto": concepto,
                "subcategoria": subcategoria,
                "plazos": plazos,
                "fecha_compra": fecha_compra,
            }

            # -------------------------
            # FALTA DESCRIPCIÓN
            # -------------------------

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

            # -------------------------
            # GASTO SIN CUENTA
            # -------------------------

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

            # -------------------------
            # VALIDAR TARJETA
            # -------------------------

            if (
                tipo_movimiento == "Gasto"
                and cuenta not in CUENTAS_GASTO
            ):

                # Puede ocurrir si encuentra
                # una cuenta histórica.
                context.user_data[
                    "gasto_pendiente"
                ][
                    "cuenta"
                ] = None

                await update.message.reply_text(
                    (
                        "Esa cuenta ya no está "
                        "entre tus tarjetas de gasto.\n\n"
                        "Selecciona la tarjeta:"
                    ),
                    reply_markup=(
                        crear_teclado_cuentas()
                    )
                )

                return

            # -------------------------
            # SUBCATEGORÍA DETECTADA
            # -------------------------

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

            # -------------------------
            # PEDIR CATEGORÍA
            # -------------------------

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
                f"Tipo: "
                f"{tipo_movimiento}\n"
                f"Descripción: "
                f"{concepto}\n"
                f"Monto: "
                f"${monto:,.2f}\n"
                f"Cuenta: "
                f"{cuenta}\n"
                f"Tipo de pago: "
                f"{tipo_pago}\n"
                f"Plazos: "
                f"{detalle_pago}\n\n"
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

        # ====================================================
        # CONSULTAR
        # ====================================================

        mes = datos.get(
            "mes"
        )

        anio = datos.get(
            "anio"
        )

        subcategoria = datos.get(
            "subcategoria"
        )

        cuenta = datos.get(
            "cuenta"
        )

        status = datos.get(
            "status"
        )

        tipo_pago = datos.get(
            "tipo_pago"
        )

        tipo_movimiento = datos.get(
            "tipo_movimiento",
            "Gasto"
        )

        mensaje_normalizado = normalizar_texto(
            mensaje_usuario
        )

        consulta_detalle_msi = (
            tipo_pago == "Meses"
            and (
                "que mensualidades" in mensaje_normalizado
                or "cuales mensualidades" in mensaje_normalizado
                or "que pagos" in mensaje_normalizado
                or "cuales pagos" in mensaje_normalizado
            )
        )

        # -------------------------
        # SIN FILTROS
        # -------------------------

        if (
            mes is None
            and anio is None
            and subcategoria is None
            and cuenta is None
            and status is None
            and tipo_pago is None
        ):

            await update.message.reply_text(
                (
                    "No pude identificar "
                    "qué quieres consultar."
                )
            )

            return

        if consulta_detalle_msi:

            movimientos_filtrados = (
                obtener_movimientos_filtrados(
                    movimientos,
                    mes=mes,
                    anio=anio,
                    subcategoria=subcategoria,
                    cuenta=cuenta,
                    status=status,
                    tipo_pago=tipo_pago,
                    tipo_movimiento=tipo_movimiento
                )
            )

            resumen = crear_resumen_mensualidades(
                movimientos_filtrados
            )

            if resumen is None:

                await update.message.reply_text(
                    "No encontré mensualidades pendientes para ese periodo."
                )

                return

            await update.message.reply_text(
                resumen
            )

            return

        # -------------------------
        # CALCULAR TOTAL
        # -------------------------

        total = calcular_total(
            movimientos,
            mes=mes,
            anio=anio,
            subcategoria=subcategoria,
            cuenta=cuenta,
            status=status,
            tipo_pago=tipo_pago,
            tipo_movimiento=tipo_movimiento
        )

        # -------------------------
        # CONSTRUIR DESCRIPCIÓN
        # -------------------------

        partes = []

        if subcategoria is not None:

            partes.append(
                f"en {subcategoria}"
            )

        if cuenta is not None:

            partes.append(
                f"con {cuenta}"
            )

        if tipo_pago == "Meses":

            partes.append(
                "en compras a meses"
            )

        elif tipo_pago == "Contado":

            partes.append(
                "en compras de contado"
            )

        if mes is not None:

            ahora = datetime.now()

            if (
                mes == ahora.month
                and anio == ahora.year
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

        # -------------------------
        # TOTAL = 0
        # -------------------------

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
                    f"{inicio} "
                    f"{detalle}."
                )

            else:

                respuesta = (
                    f"{inicio}."
                )

        # -------------------------
        # TOTAL > 0
        # -------------------------

        else:

            if tipo_movimiento == "Ingreso":

                inicio = (
                    "Total de ingresos: "
                    f"${total:,.2f}"
                )

            elif status == "Pendiente":

                inicio = (
                    f"Tienes "
                    f"${total:,.2f} "
                    "pendiente"
                )

            elif status == "Pagado":

                inicio = (
                    f"Tienes "
                    f"${total:,.2f} "
                    "pagado"
                )

            else:

                inicio = (
                    "Total de gastos: "
                    f"${total:,.2f}"
                )

            if detalle:

                respuesta = (
                    f"{inicio} "
                    f"{detalle}."
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
            "Error procesando mensaje: "
            f"{error}"
        )

        await update.message.reply_text(
            (
                "Ocurrió un error al "
                "procesar tu mensaje."
            )
        )


# ============================================================
# SELECCIÓN DE CUENTA
# ============================================================

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
            (
                "El movimiento pendiente "
                "ya no existe."
            )
        )

        return

    tipo_movimiento = datos.get(
        "tipo_movimiento",
        "Gasto"
    )

    # -------------------------
    # INGRESOS
    # -------------------------

    if tipo_movimiento == "Ingreso":

        cuenta = (
            CUENTA_INGRESOS
        )

    # -------------------------
    # GASTOS
    # -------------------------

    else:

        cuenta = query.data.replace(
            "cuenta:",
            "",
            1
        )

        if cuenta not in CUENTAS_GASTO:

            await query.edit_message_text(
                (
                    "La cuenta seleccionada "
                    "no es válida."
                )
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

    # -------------------------
    # CATEGORÍA YA CONOCIDA
    # -------------------------

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

    # -------------------------
    # PEDIR CATEGORÍA
    # -------------------------

    await query.edit_message_text(
        (
            f"Cuenta: "
            f"{cuenta}\n\n"
            "Ahora selecciona "
            "la categoría:"
        ),
        reply_markup=(
            crear_teclado_categorias(
                tipo_movimiento
            )
        )
    )


# ============================================================
# SELECCIÓN DE CATEGORÍA
# ============================================================

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
            (
                "El movimiento pendiente "
                "ya no existe."
            )
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


# ============================================================
# CONFIRMAR MOVIMIENTO
# ============================================================

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
            (
                "No hay ningún movimiento "
                "pendiente."
            )
        )

        return

    tipo_movimiento = datos.get(
        "tipo_movimiento",
        "Gasto"
    )

    # ========================================================
    # VALIDAR CUENTA
    # ========================================================

    if tipo_movimiento == "Ingreso":

        datos[
            "cuenta"
        ] = CUENTA_INGRESOS

    elif datos.get(
        "cuenta"
    ) not in CUENTAS_GASTO:

        await query.edit_message_text(
            (
                "La cuenta del gasto "
                "no es válida."
            )
        )

        return

    # ========================================================
    # FECHAS
    # ========================================================

    fecha_compra = datos.get(
        "fecha_compra",
        datetime.now()
    )

    fecha_actual = (
        f"{fecha_compra.day}/"
        f"{fecha_compra.month}/"
        f"{fecha_compra.year}"
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

    try:

        # ====================================================
        # GASTO A MESES
        # ====================================================

        if (
            tipo_movimiento == "Gasto"
            and plazos > 1
        ):

            cuotas = generar_cuotas(
                datos["monto"],
                plazos,
                fecha_compra,
                datos["concepto"],
                datos["cuenta"]
            )

            filas = []

            for cuota in cuotas:

                fecha_cuota = (
                    f"{cuota['fecha'].day}/"
                    f"{cuota['fecha'].month}/"
                    f"{cuota['fecha'].year}"
                )

                fila = [
                    "Gasto",
                    fecha_cuota,
                    cuota["monto"],
                    datos["cuenta"],
                    "",
                    cuota["descripcion"],
                    datos["categoria"],
                    "Meses",
                    plazos,
                    "Pendiente",
                ]

                filas.append(
                    fila
                )

            print(
                "Registrando "
                f"{len(filas)} "
                "mensualidades..."
            )

            registrar_movimientos(
                filas
            )

        # ====================================================
        # CONTADO O INGRESO
        # ====================================================

        else:

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

            registrar_movimiento(
                fila
            )

        # ====================================================
        # LIMPIAR ESTADO
        # ====================================================

        context.user_data.pop(
            "gasto_pendiente",
            None
        )

        context.user_data.pop(
            "esperando_descripcion",
            None
        )

        # ====================================================
        # RESPUESTA MSI
        # ====================================================

        if (
            tipo_movimiento == "Gasto"
            and plazos > 1
        ):

            primera_cuota = (
                cuotas[0]
            )

            ultima_cuota = (
                cuotas[-1]
            )

            mensualidad = (
                primera_cuota[
                    "monto"
                ]
            )

            fecha_corte = (
                calcular_fecha_corte(
                    fecha_compra,
                    datos["cuenta"]
                )
            )

            respuesta = (
                "Compra a meses "
                "registrada ✅\n\n"
                f"Descripción: "
                f"{datos['concepto']}\n"
                f"Monto total: "
                f"${datos['monto']:,.2f}\n"
                f"Cuenta: "
                f"{datos['cuenta']}\n"
                f"Categoría: "
                f"{datos['categoria']}\n"
                f"Plazos: "
                f"{plazos}\n"
                f"Mensualidad: "
                f"${mensualidad:,.2f}\n"
            )

            if fecha_corte is not None:

                respuesta += (
                    f"Corte aplicable: "
                    f"{fecha_corte.strftime('%d/%m/%Y')}"
                    "\n"
                )

            respuesta += (
                f"Primer pago: "
                f"{primera_cuota['fecha'].strftime('%d/%m/%Y')}"
                "\n"
                f"Último pago: "
                f"{ultima_cuota['fecha'].strftime('%d/%m/%Y')}"
                "\n\n"
                f"Se crearon "
                f"{plazos} mensualidades."
            )

        # ====================================================
        # RESPUESTA NORMAL
        # ====================================================

        else:

            respuesta = (
                "Movimiento registrado ✅\n\n"
                f"Tipo: "
                f"{tipo_movimiento}\n"
                f"Descripción: "
                f"{datos['concepto']}\n"
                f"Monto: "
                f"${datos['monto']:,.2f}\n"
                f"Cuenta: "
                f"{datos['cuenta']}\n"
                f"Categoría: "
                f"{datos['categoria']}\n"
                f"Tipo de pago: "
                f"{tipo_pago}\n"
                f"Plazos: "
                f"{plazos}\n"
                f"Status: "
                f"{status}"
            )

        await query.edit_message_text(
            respuesta
        )

    except Exception as error:

        print(
            "Error registrando movimiento: "
            f"{error}"
        )

        await query.edit_message_text(
            (
                "No pude registrar "
                "el movimiento."
            )
        )


# ============================================================
# CANCELAR MOVIMIENTO
# ============================================================

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


# ============================================================
# ERRORES
# ============================================================

async def manejar_error(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "Error de Telegram: "
        f"{context.error}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not TOKEN:

        raise RuntimeError(
            "No se encontró "
            "TELEGRAM_TOKEN."
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
            pattern=(
                r"^confirmar_gasto$"
            )
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            cancelar_gasto,
            pattern=(
                r"^cancelar_gasto$"
            )
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