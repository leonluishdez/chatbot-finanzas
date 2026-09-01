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
    normalizar_texto,
    NOMBRES_MESES
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv()

TOKEN = os.getenv(
    "TELEGRAM_TOKEN"
)


# ============================================================
# CUENTAS
# ============================================================

CUENTA_INGRESOS = (
    "BBVA Debito"
)

CUENTAS_GASTO = [
    "BBVA Platinum",
    "Citibanamex Oro",
    "Citibanamex Costco",
    "Invex",
]


# ============================================================
# CATEGORÍAS
# ============================================================

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


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

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


# ============================================================
# TECLADO DE CATEGORÍAS
# ============================================================

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


# ============================================================
# TECLADO DE CUENTAS
# ============================================================

def crear_teclado_cuentas():

    teclado = []
    fila = []

    for cuenta in CUENTAS_GASTO:

        boton = InlineKeyboardButton(
            cuenta,
            callback_data=(
                f"cuenta:{cuenta}"
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


# ============================================================
# TECLADO DE CONFIRMACIÓN
# ============================================================

def crear_teclado_confirmacion():

    return InlineKeyboardMarkup(
        [
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
    )


# ============================================================
# RESUMEN DE CONFIRMACIÓN
# ============================================================

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
        f"Descripción: {datos['concepto']}\n"
        f"Monto: ${datos['monto']:,.2f}\n"
        f"Cuenta: {datos['cuenta']}\n"
        f"Categoría: {datos['categoria']}\n"
        f"Tipo de pago: {tipo_pago}\n"
        f"Plazos: {plazos}\n"
        f"Status: {status}"
    )

    if (
        tipo_movimiento == "Gasto"
        and plazos > 1
    ):

        fecha_compra = datos.get(
            "fecha_compra",
            datetime.now()
        )

        fecha_corte = calcular_fecha_corte(
            fecha_compra,
            datos["cuenta"]
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
                "Corte aplicable: "
                f"{fecha_corte.strftime('%d/%m/%Y')}"
            )

        if primera_fecha_pago is not None:

            resumen += (
                "\n"
                "Primer pago: "
                f"{primera_fecha_pago.strftime('%d/%m/%Y')}"
            )

    return resumen


# ============================================================
# RESUMEN DE MENSUALIDADES
# ============================================================

def crear_resumen_mensualidades(
    movimientos
):

    if not movimientos:

        return None

    movimientos_validos = []

    for movimiento in movimientos:

        try:

            fecha = convertir_fecha(
                movimiento.get(
                    "Fecha de Pago",
                    ""
                )
            )

        except ValueError:

            continue

        movimiento_copia = dict(
            movimiento
        )

        movimiento_copia[
            "_fecha"
        ] = fecha

        movimientos_validos.append(
            movimiento_copia
        )

    movimientos_ordenados = sorted(
        movimientos_validos,
        key=lambda movimiento: (
            movimiento["_fecha"]
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

        if not descripcion:

            descripcion = (
                "Sin descripción"
            )

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

        fecha = movimiento[
            "_fecha"
        ]

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

    if not movimientos_por_cuenta:

        return None

    lineas = [
        "💳 Mensualidades pendientes",
        ""
    ]

    for (
        cuenta,
        cargos
    ) in movimientos_por_cuenta.items():

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
            (
                f"Subtotal: "
                f"${subtotal:,.2f}"
            )
        )

        lineas.append(
            ""
        )

    lineas.append(
        (
            f"Total: "
            f"${total_general:,.2f}"
        )
    )

    return "\n".join(
        lineas
    )


# ============================================================
# RESUMEN DE PROYECCIÓN
# ============================================================

def crear_resumen_proyeccion(
    movimientos,
    periodos,
    subcategoria=None,
    cuenta=None,
    status=None,
    tipo_pago=None,
    tipo_movimiento="Gasto"
):

    resultados = []

    total_general = 0.0

    for periodo in periodos:

        numero_mes = periodo[
            "mes"
        ]

        anio = periodo[
            "anio"
        ]

        total_mes = calcular_total(
            movimientos,
            mes=numero_mes,
            anio=anio,
            subcategoria=subcategoria,
            cuenta=cuenta,
            status=status,
            tipo_pago=tipo_pago,
            tipo_movimiento=tipo_movimiento
        )

        resultados.append(
            {
                "mes": numero_mes,
                "anio": anio,
                "total": total_mes,
            }
        )

        total_general += total_mes

    anios = {
        resultado["anio"]
        for resultado in resultados
    }

    mostrar_anio = (
        len(anios) > 1
    )

    lineas = [
        "📊 Compromisos próximos",
        ""
    ]

    for resultado in resultados:

        nombre_mes = NOMBRES_MESES.get(
            resultado["mes"],
            str(
                resultado["mes"]
            )
        )

        if mostrar_anio:

            etiqueta = (
                f"{nombre_mes} "
                f"{resultado['anio']}"
            )

        else:

            etiqueta = (
                nombre_mes
            )

        lineas.append(
            (
                f"{etiqueta}: "
                f"${resultado['total']:,.2f}"
            )
        )

    lineas.append(
        ""
    )

    lineas.append(
        (
            "Total comprometido: "
            f"${total_general:,.2f}"
        )
    )

    return "\n".join(
        lineas
    )


# ============================================================
# RESPONDER MENSAJE
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
    # ESPERANDO DESCRIPCIÓN
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
                (
                    "El movimiento pendiente "
                    "ya no existe."
                )
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

        if tipo_movimiento == "Ingreso":

            movimiento_pendiente[
                "cuenta"
            ] = CUENTA_INGRESOS

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

            if tipo_movimiento == "Ingreso":

                cuenta = CUENTA_INGRESOS
                plazos = 1

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

            if (
                tipo_movimiento == "Gasto"
                and cuenta not in CUENTAS_GASTO
            ):

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

            if subcategoria is not None:

                movimiento_pendiente = (
                    context.user_data[
                        "gasto_pendiente"
                    ]
                )

                movimiento_pendiente[
                    "categoria"
                ] = subcategoria

                await update.message.reply_text(
                    crear_resumen_confirmacion(
                        movimiento_pendiente
                    ),
                    reply_markup=(
                        crear_teclado_confirmacion()
                    )
                )

                return

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

        # ====================================================
        # CONSULTAR
        # ====================================================

        mes = datos.get(
            "mes"
        )

        meses = datos.get(
            "meses",
            []
        )

        periodos = datos.get(
            "periodos",
            []
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

        # ====================================================
        # CONVERTIR VARIOS MESES EXPLÍCITOS EN PERIODOS
        # ====================================================

        periodos_consulta = list(
            periodos
        )

        if (
            not periodos_consulta
            and len(meses) > 1
        ):

            periodos_consulta = [
                {
                    "mes": numero_mes,
                    "anio": anio,
                }
                for numero_mes in meses
            ]

        # ====================================================
        # PROYECCIÓN
        # ====================================================

        if periodos_consulta:

            respuesta = crear_resumen_proyeccion(
                movimientos,
                periodos_consulta,
                subcategoria=subcategoria,
                cuenta=cuenta,
                status=status,
                tipo_pago=tipo_pago,
                tipo_movimiento=tipo_movimiento
            )

            await update.message.reply_text(
                respuesta
            )

            return

        # ====================================================
        # VALIDAR CONSULTA
        # ====================================================

        if (
            mes is None
            and not meses
            and not periodos
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

        # ====================================================
        # DETALLE DE MENSUALIDADES
        # ====================================================

        mensaje_normalizado = (
            normalizar_texto(
                mensaje_usuario
            )
        )

        consulta_detalle_msi = (
            tipo_pago == "Meses"
            and (
                "que mensualidades"
                in mensaje_normalizado

                or "cuales mensualidades"
                in mensaje_normalizado

                or "que pagos"
                in mensaje_normalizado

                or "cuales pagos"
                in mensaje_normalizado
            )
        )

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

            resumen = (
                crear_resumen_mensualidades(
                    movimientos_filtrados
                )
            )

            if resumen is None:

                await update.message.reply_text(
                    (
                        "No encontré mensualidades "
                        "pendientes para ese periodo."
                    )
                )

                return

            await update.message.reply_text(
                resumen
            )

            return

        # ====================================================
        # TOTAL NORMAL
        # ====================================================

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

            nombre_mes = NOMBRES_MESES.get(
                mes,
                str(mes)
            )

            partes.append(
                (
                    f"en {nombre_mes.lower()} "
                    f"de {anio}"
                )
            )

        detalle = " ".join(
            partes
        )

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

        else:

            if tipo_movimiento == "Ingreso":

                inicio = (
                    "Total de ingresos: "
                    f"${total:,.2f}"
                )

            elif status == "Pendiente":

                inicio = (
                    f"Tienes ${total:,.2f} "
                    "pendiente"
                )

            elif status == "Pagado":

                inicio = (
                    f"Tienes ${total:,.2f} "
                    "pagado"
                )

            else:

                inicio = (
                    "Total de gastos: "
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

    if tipo_movimiento == "Ingreso":

        cuenta = CUENTA_INGRESOS

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

    if subcategoria is not None:

        datos[
            "categoria"
        ] = subcategoria

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
# CONFIRMAR
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
        # MSI
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
                (
                    "Registrando "
                    f"{len(filas)} "
                    "mensualidades..."
                )
            )

            registrar_movimientos(
                filas
            )

        # ====================================================
        # CONTADO / INGRESO
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
                    "Corte aplicable: "
                    f"{fecha_corte.strftime('%d/%m/%Y')}"
                    "\n"
                )

            respuesta += (
                "Primer pago: "
                f"{primera_cuota['fecha'].strftime('%d/%m/%Y')}"
                "\n"
                "Último pago: "
                f"{ultima_cuota['fecha'].strftime('%d/%m/%Y')}"
                "\n\n"
                f"Se crearon "
                f"{plazos} mensualidades."
            )

        else:

            respuesta = (
                "Movimiento registrado ✅\n\n"
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

        await query.edit_message_text(
            respuesta
        )

    except Exception as error:

        print(
            (
                "Error registrando movimiento: "
                f"{error}"
            )
        )

        await query.edit_message_text(
            (
                "No pude registrar "
                "el movimiento."
            )
        )


# ============================================================
# CANCELAR
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
        (
            "Error de Telegram: "
            f"{context.error}"
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not TOKEN:

        raise RuntimeError(
            (
                "No se encontró "
                "TELEGRAM_TOKEN."
            )
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