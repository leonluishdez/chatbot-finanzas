from finanzas import formatear_fecha
import os

from recurrentes import leer_reglas, generar_vencimientos, procesar_comando
from recurrentes_guiado import manejar_texto_recurrente, manejar_boton_recurrente
from recordatorios import (
    activar as activar_recordatorios,
    configurar_recordatorios,
    crear_mensaje as crear_mensaje_recordatorio,
    desactivar as desactivar_recordatorios,
    vencimientos_pendientes,
)

from datetime import datetime, timedelta

from dotenv import load_dotenv

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from sheets import (
    actualizar_subcategoria_movimiento,
    obtener_estados_cuenta,
    obtener_movimientos,
    obtener_movimientos_sin_clasificar,
    registrar_estado_cuenta,
    registrar_movimiento,
    registrar_movimientos
)

from finanzas import (
    NOMBRES_MESES,
    calcular_promedio_ingresos_recientes,
    analizar_gasto_por_subcategoria,
    calcular_fecha_corte,
    calcular_fechas_estado_cuenta,
    calcular_primera_fecha_pago,
    calcular_total,
    calcular_total_fecha_pago,
    convertir_fecha,
    convertir_monto,
    generar_cuotas,
    interpretar_estado_cuenta,
    interpretar_mensaje,
    normalizar_texto,
    obtener_movimientos_filtrados,
    buscar_estado_cuenta,
    interpretar_consulta_estado_cuenta,
    obtener_movimientos_fecha_pago,
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
    "PPR",
    "Amazon",
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
# FUNCIONES BÁSICAS
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
                ),
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


    # ========================================================
    # DATOS DE TARJETA
    # ========================================================

    if tipo_movimiento == "Gasto":

        fecha_compra = datos.get(
            "fecha_compra",
            datetime.now()
        )

        fecha_corte = calcular_fecha_corte(
            fecha_compra,
            datos[
                "cuenta"
            ]
        )

        fecha_pago = (
            calcular_primera_fecha_pago(
                fecha_compra,
                datos[
                    "cuenta"
                ]
            )
        )

        if fecha_corte is not None:

            resumen += (
                "\n"
                "Corte aplicable: "
                f"{formatear_fecha(fecha_corte)}"
            )

        if fecha_pago is not None:

            if plazos > 1:

                etiqueta = (
                    "Primer pago"
                )

            else:

                etiqueta = (
                    "Fecha de pago"
                )

            resumen += (
                f"\n{etiqueta}: "
                f"{formatear_fecha(fecha_pago)}"
            )

        if plazos > 1:

            mensualidad = round(
                datos[
                    "monto"
                ]
                / plazos,
                2
            )

            resumen += (
                "\n"
                "Mensualidad aproximada: "
                f"${mensualidad:,.2f}"
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

        copia = dict(
            movimiento
        )

        copia[
            "_fecha"
        ] = fecha

        movimientos_validos.append(
            copia
        )


    if not movimientos_validos:

        return None


    movimientos_validos.sort(
        key=lambda movimiento:
        movimiento[
            "_fecha"
        ]
    )


    movimientos_por_cuenta = {}

    total_general = 0.0


    for movimiento in movimientos_validos:

        cuenta = str(
            movimiento.get(
                "Cuenta",
                "Sin cuenta"
            )
        ).strip()

        if not cuenta:

            cuenta = (
                "Sin cuenta"
            )


        descripcion = str(
            movimiento.get(
                "Descripcion",
                ""
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

                "fecha": movimiento[
                    "_fecha"
                ],
            }
        )


        total_general += monto


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
                    f"• "
                    f"{cargo['descripcion']} "

                    f"— "
                    f"${cargo['monto']:,.2f} "

                    f"("
                    f"{formatear_fecha(cargo['fecha'])}"
                    f")"
                )
            )

            subtotal += cargo[
                "monto"
            ]


        lineas.append(
            (
                "Subtotal: "
                f"${subtotal:,.2f}"
            )
        )

        lineas.append(
            ""
        )


    lineas.append(
        (
            "Total: "
            f"${total_general:,.2f}"
        )
    )


    return "\n".join(
        lineas
    )


# ============================================================
# RESUMEN DE ANÁLISIS MENSUAL
# ============================================================

def crear_resumen_analisis_mensual(
    movimientos,
    mes=None,
    anio=None,
    cuenta=None,
    hoy=None,
):
    analisis = analizar_gasto_por_subcategoria(
        movimientos,
        mes=mes,
        anio=anio,
        cuenta=cuenta,
        hoy=hoy,
    )
    nombre_mes = NOMBRES_MESES[analisis["mes"]]
    periodo = f"{nombre_mes} {analisis['anio']}"
    comparacion = (
        f"hasta el día {analisis['dia_comparable']}"
        if analisis["es_mes_en_curso"]
        else "mes completo"
    )
    lineas = [
        f"📊 Cómo vas en {periodo}",
        f"Gasto acumulado: ${analisis['total_actual']:,.2f}",
        f"Media comparable de los 3 meses anteriores: ${analisis['total_promedio']:,.2f}",
        f"Comparación: {comparacion}.",
        "",
        "Por rubro:",
    ]

    if not analisis["categorias"]:
        return "\n".join(lineas + ["Aún no hay gastos con fechas válidas para analizar."])

    for categoria in analisis["categorias"][:8]:
        variacion = (
            f"{categoria['porcentaje']:+.1f}%"
            if categoria["porcentaje"] is not None
            else "sin base comparable"
        )
        signo = "+" if categoria["diferencia"] >= 0 else "-"
        lineas.extend([
            f"• {categoria['subcategoria']}: ${categoria['actual']:,.2f}",
            f"  Media: ${categoria['promedio']:,.2f} | Diferencia: {signo}${abs(categoria['diferencia']):,.2f} ({variacion})",
        ])

    oportunidades = [
        categoria for categoria in analisis["categorias"]
        if categoria["diferencia"] > 0 and categoria["promedio"] > 0
    ]
    ajustables = [
        categoria for categoria in oportunidades
        if categoria["flexibilidad"] == "ajustable"
    ]
    fijos = [
        categoria for categoria in oportunidades
        if categoria["flexibilidad"] == "compromiso/fijo"
    ]

    if ajustables:
        lineas.extend(["", "💡 Ajustes concretos:"])
        for categoria in sorted(ajustables, key=lambda item: item["diferencia"], reverse=True)[:3]:
            lineas.append(
                f"• {categoria['subcategoria']}: llevas ${categoria['diferencia']:,.2f} por encima de tu media comparable. "
                f"Si quieres acercarte a tu ritmo habitual al cierre, limita compras adicionales de este rubro por ${categoria['diferencia']:,.2f}."
            )

    if fijos:
        lineas.extend(["", "Compromisos que subieron:"])
        for categoria in sorted(fijos, key=lambda item: item["diferencia"], reverse=True)[:3]:
            lineas.append(
                f"• {categoria['subcategoria']}: +${categoria['diferencia']:,.2f}. Lo marco como compromiso/fijo; conviene revisarlo, no recortarlo automáticamente."
            )

    return "\n".join(lineas)


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
    tipo_movimiento="Gasto",
    hoy=None,
    reglas_recurrentes=None
):

    hoy = hoy or datetime.now()
    periodos = list(periodos)
    es_proyeccion = (
        bool(periodos)
        and normalizar_texto(tipo_movimiento) == "gasto"
        and normalizar_texto(status or "") == "pendiente"
        and all(
            (p["anio"] or hoy.year, p["mes"]) > (hoy.year, hoy.month)
            for p in periodos
        )
    )
    ingreso_estimado = (
        calcular_promedio_ingresos_recientes(movimientos, hoy=hoy)
        if es_proyeccion else 0.0
    )

    estimaciones = []
    if es_proyeccion:
        reglas = leer_reglas() if reglas_recurrentes is None else reglas_recurrentes
        estimaciones = generar_vencimientos(reglas, movimientos, periodos, hoy=hoy)
        movimientos = list(movimientos) + estimaciones

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


        total_recurrente = calcular_total(
            estimaciones, mes=numero_mes, anio=anio, subcategoria=subcategoria,
            cuenta=cuenta, status=status, tipo_pago=tipo_pago,
            tipo_movimiento=tipo_movimiento
        )

        resultados.append(
            {
                "mes": numero_mes,

                "anio": anio,

                "total": total_mes,
                "recurrente": total_recurrente,
            }
        )


        total_general += total_mes


    anios = {

        resultado[
            "anio"
        ]

        for resultado
        in resultados
    }


    mostrar_anio = (
        len(
            anios
        )
        > 1
    )


    lineas = [
        "📊 Compromisos próximos",
        ""
    ]


    if es_proyeccion:
        lineas = [
            "📊 Proyección financiera",
            f"Ingreso mensual estimado: ${ingreso_estimado:,.2f}",
            "Promedio de los últimos 3 meses completos (meses sin ingresos = $0).",
            "",
        ]
        if any(filtro is not None for filtro in (subcategoria, cuenta, tipo_pago)):
            lineas.extend([
                "Compromisos filtrados; ingreso estimado de todas las cuentas.",
                "El disponible solo descuenta los gastos seleccionados.",
                "",
            ])

    for resultado in resultados:

        nombre_mes = NOMBRES_MESES.get(
            resultado[
                "mes"
            ],
            str(
                resultado[
                    "mes"
                ]
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


        if es_proyeccion:
            lineas.extend([
                etiqueta,
                f"Comprometido: ${resultado['total']:,.2f}",
                f"Disponible estimado: ${ingreso_estimado - resultado['total']:,.2f}",
                "",
            ])
            if resultado['recurrente']:
                lineas.insert(-1, f"Incluye recurrentes estimados: ${resultado['recurrente']:,.2f}")
            continue

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


    if es_proyeccion:
        ingreso_periodo = round(ingreso_estimado * len(resultados), 2)
        lineas.extend([
            f"Ingreso estimado del periodo: ${ingreso_periodo:,.2f}",
            f"Disponible estimado del periodo: ${ingreso_periodo - total_general:,.2f}",
        ])

    return "\n".join(
        lineas
    )


# ============================================================
# REGISTRAR Y CONCILIAR ESTADO DE CUENTA
# ============================================================

async def registrar_estado_desde_mensaje(
    update,
    mensaje_usuario,
    movimientos
):

    datos_estado = interpretar_estado_cuenta(
        mensaje_usuario,
        movimientos
    )


    if datos_estado is None:

        return False


    cuenta = datos_estado.get(
        "cuenta"
    )

    mes = datos_estado.get(
        "mes"
    )

    anio = datos_estado.get(
        "anio"
    )

    monto_banco = datos_estado.get(
        "monto"
    )


    # ========================================================
    # VALIDACIONES
    # ========================================================

    if cuenta is None:

        await update.message.reply_text(
            (
                "No pude identificar "
                "la tarjeta."
            )
        )

        return True


    if (
        mes is None
        or anio is None
    ):

        await update.message.reply_text(
            (
                "No pude identificar "
                "el periodo del estado."
            )
        )

        return True


    if monto_banco is None:

        await update.message.reply_text(
            (
                "No pude identificar "
                "el pago para no generar intereses."
            )
        )

        return True


    # ========================================================
    # CALCULAR CORTE Y PAGO
    # ========================================================

    fecha_corte, fecha_pago = (
        calcular_fechas_estado_cuenta(
            cuenta,
            mes,
            anio
        )
    )


    # ========================================================
    # CALCULAR LO CAPTURADO
    # ========================================================

    capturado = calcular_total_fecha_pago(
        movimientos,
        cuenta,
        fecha_pago
    )


    # ========================================================
    # DIFERENCIA
    # ========================================================

    diferencia = round(
        monto_banco
        - capturado,
        2
    )


    if abs(
        diferencia
    ) <= 0.01:

        status_conciliacion = (
            "Conciliado"
        )

    else:

        status_conciliacion = (
            "Revisar"
        )


    # ========================================================
    # PERIODO
    # ========================================================

    periodo = (
        f"{NOMBRES_MESES[mes].lower()} "
        f"{anio}"
    )


    fecha_corte_texto = formatear_fecha(fecha_corte)


    fecha_pago_texto = formatear_fecha(fecha_pago)


    # ========================================================
    # GUARDAR EN ESTADOSCUENTA
    # ========================================================

    fila_estado = [

        cuenta,

        periodo,

        fecha_corte_texto,

        fecha_pago_texto,

        monto_banco,

        status_conciliacion,
    ]


    registrar_estado_cuenta(
        fila_estado
    )


    # ========================================================
    # RESULTADO
    # ========================================================

    if abs(
        diferencia
    ) <= 0.01:

        resultado_conciliacion = (
            "✅ CONCILIADO"
        )


    elif diferencia > 0:

        resultado_conciliacion = (
            "⚠️ REVISAR\n"

            "El banco reporta "

            f"${diferencia:,.2f} "

            "más que tus movimientos."
        )


    else:

        diferencia_absoluta = abs(
            diferencia
        )

        resultado_conciliacion = (
            "⚠️ REVISAR\n"

            "Tienes "

            f"${diferencia_absoluta:,.2f} "

            "más capturado que lo "

            "reportado por el banco."
        )


    await update.message.reply_text(
        (
            "🔍 Conciliación del estado\n\n"

            f"Cuenta: "
            f"{cuenta}\n"

            f"Periodo: "
            f"{periodo}\n"

            "Fecha de corte: "
            f"{formatear_fecha(fecha_corte)}\n"

            "Fecha límite: "
            f"{formatear_fecha(fecha_pago)}\n\n"

            "Banco: "
            f"${monto_banco:,.2f}\n"

            "Capturado: "
            f"${capturado:,.2f}\n"

            "Diferencia: "
            f"${diferencia:,.2f}\n\n"

            f"{resultado_conciliacion}"
        )
    )


    return True


# ============================================================
# CONTINUAR DESCRIPCIÓN PENDIENTE
# ============================================================

async def continuar_movimiento_pendiente(
    update,
    context,
    mensaje_usuario
):

    if not context.user_data.get(
        "esperando_descripcion"
    ):

        return False


    datos = context.user_data.get(
        "gasto_pendiente"
    )


    if datos is None:

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

        return True


    datos[
        "concepto"
    ] = (
        mensaje_usuario
        .strip()
        .capitalize()
    )


    context.user_data[
        "gasto_pendiente"
    ] = datos


    context.user_data.pop(
        "esperando_descripcion",
        None
    )


    tipo_movimiento = datos.get(
        "tipo_movimiento",
        "Gasto"
    )


    # ========================================================
    # INGRESO
    # ========================================================

    if tipo_movimiento == "Ingreso":

        datos[
            "cuenta"
        ] = CUENTA_INGRESOS


    # ========================================================
    # GASTO SIN CUENTA
    # ========================================================

    elif datos.get(
        "cuenta"
    ) is None:

        await update.message.reply_text(
            (
                f"Descripción: "
                f"{datos['concepto']}\n\n"

                "Selecciona la tarjeta "
                "que usaste:"
            ),
            reply_markup=(
                crear_teclado_cuentas()
            )
        )

        return True


    # ========================================================
    # SUBCATEGORÍA DETECTADA
    # ========================================================

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


        await update.message.reply_text(
            crear_resumen_confirmacion(
                datos
            ),
            reply_markup=(
                crear_teclado_confirmacion()
            )
        )

        return True


    # ========================================================
    # PEDIR CATEGORÍA
    # ========================================================

    await update.message.reply_text(
        (
            f"Descripción: "
            f"{datos['concepto']}\n\n"

            "Selecciona la categoría:"
        ),
        reply_markup=(
            crear_teclado_categorias(
                tipo_movimiento
            )
        )
    )


    return True

def crear_detalle_conciliacion(
    estado,
    movimientos_estado
):

    cuenta = str(
        estado.get(
            "Cuenta",
            ""
        )
    ).strip()

    periodo = str(
        estado.get(
            "Periodo",
            ""
        )
    ).strip()

    fecha_pago_texto = str(
        estado.get(
            "Fecha Limite de Pago",
            ""
        )
    ).strip()

    try:

        banco = convertir_monto(
            estado.get(
                "Pago Para No Generar Intereses",
                0
            )
        )

    except (
        ValueError,
        TypeError
    ):

        banco = 0.0

    capturado = 0.0

    cargos = []

    for movimiento in movimientos_estado:

        descripcion = str(
            movimiento.get(
                "Descripcion",
                ""
            )
        ).strip()

        if not descripcion:

            descripcion = str(
                movimiento.get(
                    "Concepto",
                    ""
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

        capturado += monto

        cargos.append(
            {
                "descripcion": descripcion,
                "monto": monto,
            }
        )

    capturado = round(
        capturado,
        2
    )

    diferencia = round(
        banco - capturado,
        2
    )

    lineas = [
        "🔍 Detalle de conciliación",
        "",
        f"Cuenta: {cuenta}",
        f"Periodo: {periodo}",
        f"Fecha límite: {fecha_pago_texto}",
        "",
        "Movimientos capturados:",
        "",
    ]

    if cargos:

        for cargo in cargos:

            lineas.append(
                (
                    f"• {cargo['descripcion']} "
                    f"— ${cargo['monto']:,.2f}"
                )
            )

    else:

        lineas.append(
            "No hay movimientos capturados."
        )

    lineas.extend(
        [
            "",
            "────────────────",
            f"Capturado: ${capturado:,.2f}",
            f"Banco: ${banco:,.2f}",
        ]
    )

    if abs(
        diferencia
    ) <= 0.01:

        lineas.extend(
            [
                "Diferencia: $0.00",
                "",
                "✅ CONCILIADO",
            ]
        )

    elif diferencia > 0:

        lineas.extend(
            [
                (
                    "Faltante por identificar: "
                    f"${diferencia:,.2f}"
                ),
                "",
                "⚠️ REVISAR",
            ]
        )

    else:

        lineas.extend(
            [
                (
                    "Capturado de más: "
                    f"${abs(diferencia):,.2f}"
                ),
                "",
                "⚠️ REVISAR",
            ]
        )

    return "\n".join(
        lineas
    )


# ============================================================
# CLASIFICAR MOVIMIENTOS IMPORTADOS
# ============================================================

def crear_teclado_clasificacion():

    teclado = []
    fila = []

    for categoria in CATEGORIAS_GASTO:

        boton = InlineKeyboardButton(
            categoria,
            callback_data=(
                f"clasificar:{categoria}"
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


def crear_texto_clasificacion(
    movimiento,
    total_pendientes
):

    descripcion = str(
        movimiento.get(
            "Descripcion",
            ""
        )
    ).strip()

    if not descripcion:

        descripcion = str(
            movimiento.get(
                "Concepto",
                ""
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

    cuenta = str(
        movimiento.get(
            "Cuenta",
            ""
        )
    ).strip()

    fecha_compra = str(
        movimiento.get(
            "Fecha de Compra",
            ""
        )
    ).strip()

    if not fecha_compra:

        fecha_compra = (
            "No disponible"
        )

    fecha_pago = str(
        movimiento.get(
            "Fecha de Pago",
            ""
        )
    ).strip()

    tipo_pago = str(
        movimiento.get(
            "Tipo de Pago",
            ""
        )
    ).strip()

    return (
        "🏷️ Movimiento sin clasificar\n\n"
        f"Pendientes: {total_pendientes}\n\n"
        f"${monto:,.2f}\n"
        f"{descripcion}\n\n"
        f"Cuenta: {cuenta}\n"
        f"Fecha de compra: {fecha_compra}\n"
        f"Fecha de pago: {fecha_pago}\n"
        f"Tipo de pago: {tipo_pago}\n\n"
        "Selecciona la subcategoría:"
    )


async def iniciar_clasificacion(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.message is None:

        return

    pendientes = (
        obtener_movimientos_sin_clasificar()
    )

    if not pendientes:

        context.user_data.pop(
            "clasificacion_pendiente",
            None
        )

        await update.message.reply_text(
            (
                "✅ No hay movimientos "
                "sin clasificar."
            )
        )

        return

    movimiento = pendientes[0]

    context.user_data[
        "clasificacion_pendiente"
    ] = {
        "fila": movimiento[
            "_fila"
        ]
    }

    await update.message.reply_text(
        crear_texto_clasificacion(
            movimiento,
            len(
                pendientes
            )
        ),
        reply_markup=(
            crear_teclado_clasificacion()
        )
    )


async def manejar_clasificacion(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query is None:

        return

    await query.answer()

    pendiente = context.user_data.get(
        "clasificacion_pendiente"
    )

    if pendiente is None:

        await query.edit_message_text(
            (
                "Ese movimiento ya no está "
                "pendiente de clasificación.\n\n"
                "Usa /clasificar para continuar."
            )
        )

        return

    categoria = query.data.replace(
        "clasificar:",
        "",
        1
    )

    if categoria not in CATEGORIAS_GASTO:

        await query.edit_message_text(
            (
                "La subcategoría seleccionada "
                "no es válida."
            )
        )

        return

    numero_fila = pendiente.get(
        "fila"
    )

    actualizado = (
        actualizar_subcategoria_movimiento(
            numero_fila,
            categoria
        )
    )

    if not actualizado:

        context.user_data.pop(
            "clasificacion_pendiente",
            None
        )

        await query.edit_message_text(
            (
                "Ese movimiento cambió antes "
                "de que pudiera clasificarlo.\n\n"
                "Usa /clasificar para continuar."
            )
        )

        return

    pendientes = (
        obtener_movimientos_sin_clasificar()
    )

    if not pendientes:

        context.user_data.pop(
            "clasificacion_pendiente",
            None
        )

        await query.edit_message_text(
            (
                f"✅ Clasificado como: "
                f"{categoria}\n\n"
                "🎉 No quedan movimientos "
                "sin clasificar."
            )
        )

        return

    siguiente = pendientes[0]

    context.user_data[
        "clasificacion_pendiente"
    ] = {
        "fila": siguiente[
            "_fila"
        ]
    }

    await query.edit_message_text(
        (
            f"✅ Clasificado como: "
            f"{categoria}\n\n"
            + crear_texto_clasificacion(
                siguiente,
                len(
                    pendientes
                )
            )
        ),
        reply_markup=(
            crear_teclado_clasificacion()
        )
    )


# ============================================================
# RESPONDER MENSAJES
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


    if await manejar_texto_recurrente(update, context, CUENTAS_GASTO, CATEGORIAS_GASTO):
        return

    # ========================================================
    # DESCRIPCIÓN PENDIENTE
    # ========================================================

    if await continuar_movimiento_pendiente(
        update,
        context,
        mensaje_usuario
    ):

        return


    print(
        f"Mensaje recibido: "
        f"{mensaje_usuario}"
    )


    try:

        movimientos = (
            obtener_movimientos()
        )


        # ====================================================
        # ESTADO DE CUENTA
        # ====================================================

        if await registrar_estado_desde_mensaje(
            update,
            mensaje_usuario,
            movimientos
        ):

            return

        # ====================================================
        # CONSULTAR DETALLE DE ESTADO
        # ====================================================

        datos_estado = (
            interpretar_consulta_estado_cuenta(
                mensaje_usuario,
                movimientos
            )
        )

        if datos_estado is not None:

            cuenta_estado = datos_estado.get(
                "cuenta"
            )

            mes_estado = datos_estado.get(
                "mes"
            )

            anio_estado = datos_estado.get(
                "anio"
            )

            if cuenta_estado is None:

                await update.message.reply_text(
                    (
                        "No pude identificar "
                        "la tarjeta del estado."
                    )
                )

                return

            if (
                mes_estado is None
                or anio_estado is None
            ):

                await update.message.reply_text(
                    (
                        "No pude identificar "
                        "el periodo del estado."
                    )
                )

                return

            estados_cuenta = (
                obtener_estados_cuenta()
            )

            estado = buscar_estado_cuenta(
                estados_cuenta,
                cuenta_estado,
                mes_estado,
                anio_estado
            )

            if estado is None:

                nombre_mes = NOMBRES_MESES[
                    mes_estado
                ]

                await update.message.reply_text(
                    (
                        "No encontré un estado "
                        f"de {cuenta_estado} "
                        f"para {nombre_mes.lower()} "
                        f"de {anio_estado}."
                    )
                )

                return

            try:

                fecha_pago_estado = convertir_fecha(
                    estado.get(
                        "Fecha Limite de Pago",
                        ""
                    )
                )

            except ValueError:

                await update.message.reply_text(
                    (
                        "La fecha límite de pago "
                        "del estado no es válida."
                    )
                )

                return

            movimientos_estado = (
                obtener_movimientos_fecha_pago(
                    movimientos,
                    cuenta_estado,
                    fecha_pago_estado
                )
            )

            respuesta = (
                crear_detalle_conciliacion(
                    estado,
                    movimientos_estado
                )
            )

            await update.message.reply_text(
                respuesta
            )

            return


        # ====================================================
        # PARSER GENERAL
        # ====================================================

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
        # REGISTRAR MOVIMIENTO
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


            # La categoría NO se asigna automáticamente.
            # Siempre se selecciona con botones.
            subcategoria = None


            plazos = datos.get(
                "plazos",
                1
            )


            fecha_compra = (
                datetime.now()
            )


            # =================================================
            # INGRESOS SIEMPRE A BBVA DÉBITO
            # =================================================

            if tipo_movimiento == "Ingreso":

                cuenta = (
                    CUENTA_INGRESOS
                )

                plazos = 1


            # =================================================
            # VALIDAR MONTO
            # =================================================

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


            # =================================================
            # GUARDAR TEMPORALMENTE
            # =================================================

            context.user_data[
                "gasto_pendiente"
            ] = {

                "tipo_movimiento":
                tipo_movimiento,

                "monto":
                monto,

                "cuenta":
                cuenta,

                "concepto":
                concepto,

                "subcategoria":
                subcategoria,

                "plazos":
                plazos,

                "fecha_compra":
                fecha_compra,
            }


            # =================================================
            # FALTA DESCRIPCIÓN
            # =================================================

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


            # =================================================
            # GASTO SIN CUENTA
            # =================================================

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


            # =================================================
            # CUENTA ANTIGUA / NO VÁLIDA
            # =================================================

            if (
                tipo_movimiento == "Gasto"
                and cuenta
                not in CUENTAS_GASTO
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


            # =================================================
            # SUBCATEGORÍA DETECTADA
            # =================================================

            if subcategoria is not None:

                pendiente = context.user_data[
                    "gasto_pendiente"
                ]


                pendiente[
                    "categoria"
                ] = subcategoria


                context.user_data[
                    "gasto_pendiente"
                ] = pendiente


                await update.message.reply_text(
                    crear_resumen_confirmacion(
                        pendiente
                    ),
                    reply_markup=(
                        crear_teclado_confirmacion()
                    )
                )

                return


            # =================================================
            # PEDIR CATEGORÍA
            # =================================================

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


            await update.message.reply_text(
                (
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
                ),
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

        if datos.get("analisis_mensual"):
            await update.message.reply_text(
                crear_resumen_analisis_mensual(
                    movimientos,
                    mes=mes,
                    anio=anio,
                    cuenta=cuenta,
                )
            )
            return


        # ====================================================
        # VARIOS MESES EXPLÍCITOS
        # ====================================================

        periodos_consulta = list(
            periodos
        )


        if (
            not periodos_consulta
            and len(
                meses
            ) > 1
        ):

            periodos_consulta = [

                {
                    "mes":
                    numero_mes,

                    "anio":
                    anio,
                }

                for numero_mes
                in meses
            ]


        # ====================================================
        # PROYECCIÓN
        # ====================================================

        if periodos_consulta:

            respuesta = (
                crear_resumen_proyeccion(
                    movimientos,

                    periodos_consulta,

                    subcategoria=(
                        subcategoria
                    ),

                    cuenta=cuenta,

                    status=status,

                    tipo_pago=tipo_pago,

                    tipo_movimiento=(
                        tipo_movimiento
                    )
                )
            )


            await update.message.reply_text(
                respuesta
            )


            return


        # ====================================================
        # SIN FILTROS
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
        # DETALLE DE MSI
        # ====================================================

        mensaje_normalizado = (
            normalizar_texto(
                mensaje_usuario
            )
        )


        consulta_detalle_msi = (

            tipo_pago == "Meses"

            and any(

                frase
                in mensaje_normalizado

                for frase in (

                    "que mensualidades",

                    "cuales mensualidades",

                    "que pagos",

                    "cuales pagos",
                )
            )
        )


        if consulta_detalle_msi:

            movimientos_filtrados = (
                obtener_movimientos_filtrados(
                    movimientos,

                    mes=mes,

                    anio=anio,

                    subcategoria=(
                        subcategoria
                    ),

                    cuenta=cuenta,

                    status=status,

                    tipo_pago=tipo_pago,

                    tipo_movimiento=(
                        tipo_movimiento
                    )
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
                str(
                    mes
                )
            )

            partes.append(
                (
                    f"en "
                    f"{nombre_mes.lower()} "
                    f"de {anio}"
                )
            )


        detalle = " ".join(
            partes
        )


        # ====================================================
        # TOTAL = 0
        # ====================================================

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
                    f" "
                    f"{status.lower()}"
                )


        # ====================================================
        # TOTAL > 0
        # ====================================================

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
            (
                "Error procesando mensaje: "
                f"{error}"
            )
        )


        await update.message.reply_text(
            (
                "Ocurrió un error al "
                "procesar tu mensaje."
            )
        )


# ============================================================
# SELECCIONAR CUENTA
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


    # ========================================================
    # INGRESO
    # ========================================================

    if tipo_movimiento == "Ingreso":

        cuenta = (
            CUENTA_INGRESOS
        )


    # ========================================================
    # GASTO
    # ========================================================

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
# SELECCIONAR CATEGORÍA
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
    # FECHA DE COMPRA
    # ========================================================

    fecha_compra = datos.get(
        "fecha_compra",
        datetime.now()
    )


    fecha_compra_texto = formatear_fecha(fecha_compra)


    plazos = datos.get(
        "plazos",
        1
    )


    if tipo_movimiento == "Ingreso":

        plazos = 1


    try:

        # ====================================================
        # GASTO A MSI
        # ====================================================

        if (
            tipo_movimiento == "Gasto"
            and plazos > 1
        ):

            cuotas = generar_cuotas(

                datos[
                    "monto"
                ],

                plazos,

                fecha_compra,

                datos[
                    "concepto"
                ],

                datos[
                    "cuenta"
                ]
            )


            filas = []


            for cuota in cuotas:

                fecha_pago = cuota[
                    "fecha"
                ]


                fecha_pago_texto = formatear_fecha(fecha_pago)


                fila = [

                    "Gasto",

                    fecha_pago_texto,

                    fecha_compra_texto,

                    cuota[
                        "monto"
                    ],

                    datos[
                        "cuenta"
                    ],

                    "",

                    cuota[
                        "descripcion"
                    ],

                    datos[
                        "categoria"
                    ],

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
        # GASTO DE CONTADO CON TARJETA
        # ====================================================

        elif tipo_movimiento == "Gasto":

            fecha_pago = (
                calcular_primera_fecha_pago(
                    fecha_compra,
                    datos[
                        "cuenta"
                    ]
                )
            )


            if fecha_pago is None:

                raise ValueError(
                    (
                        "No pude calcular "
                        "la fecha de pago para "
                        f"{datos['cuenta']}."
                    )
                )


            fecha_pago_texto = formatear_fecha(fecha_pago)


            fila = [

                "Gasto",

                fecha_pago_texto,

                fecha_compra_texto,

                datos[
                    "monto"
                ],

                datos[
                    "cuenta"
                ],

                "",

                datos[
                    "concepto"
                ],

                datos[
                    "categoria"
                ],

                "Contado",

                1,

                "Pendiente",
            ]


            registrar_movimiento(
                fila
            )


        # ====================================================
        # INGRESO
        # ====================================================

        else:

            fila = [

                "Ingreso",

                fecha_compra_texto,

                "",

                datos[
                    "monto"
                ],

                datos[
                    "cuenta"
                ],

                "",

                datos[
                    "concepto"
                ],

                datos[
                    "categoria"
                ],

                "Contado",

                1,

                "Pagado",
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

            primera_cuota = cuotas[
                0
            ]

            ultima_cuota = cuotas[
                -1
            ]


            fecha_corte = (
                calcular_fecha_corte(
                    fecha_compra,
                    datos[
                        "cuenta"
                    ]
                )
            )


            respuesta = (
                "Compra a meses registrada ✅\n\n"

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
                f"${primera_cuota['monto']:,.2f}\n"
            )


            if fecha_corte is not None:

                respuesta += (
                    "Corte aplicable: "
                    f"{formatear_fecha(fecha_corte)}"
                    "\n"
                )


            respuesta += (
                "Primer pago: "
                f"{formatear_fecha(primera_cuota['fecha'])}"
                "\n"

                "Último pago: "
                f"{formatear_fecha(ultima_cuota['fecha'])}"
                "\n\n"

                f"Se crearon "
                f"{plazos} mensualidades."
            )


        # ====================================================
        # RESPUESTA GASTO CONTADO
        # ====================================================

        elif tipo_movimiento == "Gasto":

            fecha_pago = (
                calcular_primera_fecha_pago(
                    fecha_compra,
                    datos[
                        "cuenta"
                    ]
                )
            )


            fecha_corte = calcular_fecha_corte(
                fecha_compra,
                datos[
                    "cuenta"
                ]
            )


            respuesta = (
                "Movimiento registrado ✅\n\n"

                "Tipo: Gasto\n"

                f"Descripción: "
                f"{datos['concepto']}\n"

                f"Monto: "
                f"${datos['monto']:,.2f}\n"

                f"Cuenta: "
                f"{datos['cuenta']}\n"

                f"Categoría: "
                f"{datos['categoria']}\n"

                "Tipo de pago: Contado\n"

                "Plazos: 1\n"

                "Status: Pendiente\n"

                "Fecha de compra: "
                f"{formatear_fecha(fecha_compra)}\n"
            )


            if fecha_corte is not None:

                respuesta += (
                    "Corte aplicable: "
                    f"{formatear_fecha(fecha_corte)}"
                    "\n"
                )


            respuesta += (
                "Fecha de pago: "
                f"{formatear_fecha(fecha_pago)}"
            )


        # ====================================================
        # RESPUESTA INGRESO
        # ====================================================

        else:

            respuesta = (
                "Movimiento registrado ✅\n\n"

                "Tipo: Ingreso\n"

                f"Descripción: "
                f"{datos['concepto']}\n"

                f"Monto: "
                f"${datos['monto']:,.2f}\n"

                f"Cuenta: "
                f"{datos['cuenta']}\n"

                f"Categoría: "
                f"{datos['categoria']}\n"

                "Tipo de pago: Contado\n"

                "Plazos: 1\n"

                "Status: Pagado"
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
        (
            "Error de Telegram: "
            f"{context.error}"
        )
    )


# ============================================================
# MAIN
# ============================================================

async def manejar_recurrentes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    try:
        respuesta = procesar_comando(update.message.text)
    except ValueError as error:
        respuesta = str(error) + "\n/recurrentes ayuda"
    except Exception:
        respuesta = "No se pudo acceder a las reglas recurrentes. Revisa el almacenamiento local antes de reintentar."
    for inicio in range(0, len(respuesta), 3500):
        await update.message.reply_text(respuesta[inicio:inicio + 3500])


async def botones_recurrentes(update, context):
    await manejar_boton_recurrente(update, context, CUENTAS_GASTO, CATEGORIAS_GASTO)


async def manejar_recordatorios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or update.effective_chat is None:
        return

    partes = update.message.text.split(maxsplit=1)
    accion = partes[1].strip().lower() if len(partes) > 1 else ""
    chat_id = update.effective_chat.id

    if accion == "activar":
        activar_recordatorios(chat_id)
        await update.message.reply_text(
            "Recordatorios activados. Todos los días a las 9:00 a.m. te avisaré "
            "los gastos pendientes que vencen al día siguiente."
        )
        return

    if accion == "desactivar":
        desactivar_recordatorios(chat_id)
        await update.message.reply_text("Recordatorios desactivados para este chat.")
        return

    if accion == "probar":
        fecha = datetime.now().date() + timedelta(days=1)
        mensaje = crear_mensaje_recordatorio(
            fecha,
            vencimientos_pendientes(obtener_movimientos(), fecha),
        )
        await update.message.reply_text(mensaje or "No hay pagos pendientes para mañana.")
        return

    await update.message.reply_text(
        "Usa /recordatorios activar para recibir avisos diarios a las 9:00 a.m.\n"
        "/recordatorios probar para ver el aviso de mañana.\n"
        "/recordatorios desactivar para detenerlos."
    )


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
        .token(
            TOKEN
        )
        .post_init(configurar_recordatorios)
        .build()
    )


    app.add_handler(CommandHandler("recurrentes", manejar_recurrentes))
    app.add_handler(CommandHandler("recordatorios", manejar_recordatorios))
    app.add_handler(CallbackQueryHandler(botones_recurrentes, pattern=r"^rec:"))

    app.add_handler(
        CommandHandler(
            "clasificar",
            iniciar_clasificacion
        )
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
            manejar_clasificacion,
            pattern=r"^clasificar:"
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
