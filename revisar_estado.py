import sys

from lector_estados import (
    extraer_datos_estado,
    extraer_texto_pdf,
    extraer_resumen_cargos_abonos,
    extraer_movimientos_regulares_invex,
)

from sheets import (
    obtener_movimientos,
    registrar_movimientos,
)

from finanzas import (
    normalizar_texto,
)

from importar_estado import (
    validar_estado,
    conciliar_con_sheets,
    mostrar_analisis_msi_bbva,
    preparar_cargos_regulares_faltantes,
    conciliar_cuotas_genericas,
    analizar_proteccion_regulares,
    revisar_cargo_regular_existente,
)


# ============================================================
# 6C.5
# TIPOS DE MOVIMIENTO PERMITIDOS EN REVISIÓN
# ============================================================

TIPOS_MOVIMIENTO = {
    "1": "Gasto",
    "2": "Inversión",
    "3": "Ahorro",
    "4": "Ingreso",
    "5": "Transferencia",
}


# ============================================================
# 6C.5
# REGLAS PERSONALES
#
# Estas reglas tienen prioridad sobre las reglas genéricas
# del importador.
#
# Por ahora están aquí.
#
# En v1.5.1E las moveremos a un módulo/configuración propia.
# ============================================================

REGLAS_PERSONALES = [
    {
        "nombre": "Aportación PPR Allianz",
        "palabras": [
            "allianz mexico",
        ],
        "tipo_movimiento": "Inversión",
        "concepto": "PPR",
        "subcategoria": "Retiro / PPR",
        "confianza": "Alta",
    },
]


# ============================================================
# UTILIDADES
# ============================================================

def separador():
    print()
    print("=" * 60)
    print()


def limpiar_texto(
    valor,
):

    if valor is None:
        return ""

    return str(
        valor
    ).strip()


# ============================================================
# DETECTAR REGLA PERSONAL
# ============================================================

def detectar_regla_personal(
    descripcion,
):

    texto = normalizar_texto(
        descripcion
    )

    for regla in REGLAS_PERSONALES:

        palabras = regla.get(
            "palabras",
            [],
        )

        for palabra in palabras:

            palabra_normalizada = (
                normalizar_texto(
                    palabra
                )
            )

            if (
                palabra_normalizada
                in texto
            ):

                return regla

    return None


# ============================================================
# CREAR SUGERENCIA DE REVISIÓN
# ============================================================

def crear_sugerencia_revision(
    item,
):

    fila = item[
        "fila"
    ]

    sugerencia = {
        "tipo_movimiento": (
            fila[
                0
            ]
            or "Gasto"
        ),
        "concepto": (
            fila[
                5
            ]
            or ""
        ),
        "subcategoria": (
            fila[
                7
            ]
            or "Varios"
        ),
        "confianza": item.get(
            "confianza",
            "Baja",
        ),
        "origen": "Regla genérica",
        "regla": item.get(
            "regla"
        ),
    }

    regla_personal = (
        detectar_regla_personal(
            fila[
                6
            ]
        )
    )

    if regla_personal:

        sugerencia = {
            "tipo_movimiento": (
                regla_personal[
                    "tipo_movimiento"
                ]
            ),
            "concepto": (
                regla_personal[
                    "concepto"
                ]
            ),
            "subcategoria": (
                regla_personal[
                    "subcategoria"
                ]
            ),
            "confianza": (
                regla_personal[
                    "confianza"
                ]
            ),
            "origen": (
                "Regla personal"
            ),
            "regla": (
                regla_personal[
                    "nombre"
                ]
            ),
        }

    return sugerencia


# ============================================================
# MOSTRAR MOVIMIENTO
# ============================================================

def mostrar_movimiento_revision(
    numero,
    item,
    sugerencia,
):

    fila = item[
        "fila"
    ]

    print()

    print(
        "-" * 60
    )

    print(
        (
            f"{numero:02d}. "
            f"${float(fila[3]):,.2f}"
        )
    )

    print()

    print(
        (
            "Descripción: "
            f"{fila[6]}"
        )
    )

    print(
        (
            "Fecha compra: "
            f"{fila[2]}"
        )
    )

    print(
        (
            "Fecha pago: "
            f"{fila[1]}"
        )
    )

    print(
        (
            "Cuenta: "
            f"{fila[4]}"
        )
    )

    print()

    print(
        "DETECCIÓN ORIGINAL"
    )

    print(
        (
            "Tipo: "
            f"{fila[0]}"
        )
    )

    print(
        (
            "Subcategoría: "
            f"{item.get('categoria', '')}"
        )
    )

    print(
        (
            "Confianza: "
            f"{item.get('confianza', '')}"
        )
    )

    regla_original = item.get(
        "regla"
    )

    if regla_original:

        print(
            (
                "Regla original: "
                f"{regla_original}"
            )
        )

    print()

    print(
        "SUGERENCIA DE REVISIÓN"
    )

    print(
        (
            "Origen: "
            f"{sugerencia['origen']}"
        )
    )

    print(
        (
            "Tipo de movimiento: "
            f"{sugerencia['tipo_movimiento']}"
        )
    )

    print(
        (
            "Concepto: "
            f"{sugerencia['concepto']}"
        )
    )

    print(
        (
            "Subcategoría: "
            f"{sugerencia['subcategoria']}"
        )
    )

    print(
        (
            "Confianza: "
            f"{sugerencia['confianza']}"
        )
    )

    if sugerencia[
        "regla"
    ]:

        print(
            (
                "Regla aplicada: "
                f"{sugerencia['regla']}"
            )
        )


# ============================================================
# PEDIR TIPO DE MOVIMIENTO
# ============================================================

def pedir_tipo_movimiento(
    sugerido,
):

    while True:

        print()

        print(
            "TIPO DE MOVIMIENTO"
        )

        print()

        print(
            "1. Gasto"
        )

        print(
            "2. Inversión"
        )

        print(
            "3. Ahorro"
        )

        print(
            "4. Ingreso"
        )

        print(
            "5. Transferencia"
        )

        print()

        print(
            (
                "Enter = aceptar "
                f"'{sugerido}'"
            )
        )

        print(
            "s = omitir movimiento"
        )

        respuesta = input(
            "> "
        ).strip()

        if respuesta.lower() == "s":

            return None

        if respuesta == "":

            return sugerido

        if respuesta in TIPOS_MOVIMIENTO:

            return TIPOS_MOVIMIENTO[
                respuesta
            ]

        # También permitimos escribir
        # directamente un tipo válido.

        for tipo in TIPOS_MOVIMIENTO.values():

            if (
                normalizar_texto(
                    respuesta
                )
                ==
                normalizar_texto(
                    tipo
                )
            ):

                return tipo

        print()

        print(
            "⚠️ Opción no válida."
        )


# ============================================================
# PEDIR CONCEPTO
# ============================================================

def pedir_concepto(
    sugerido,
):

    print()

    print(
        "CONCEPTO"
    )

    if sugerido:

        print(
            (
                "Enter = aceptar "
                f"'{sugerido}'"
            )
        )

    else:

        print(
            (
                "Enter = dejar concepto vacío"
            )
        )

    print(
        (
            "También puedes escribir "
            "otro concepto."
        )
    )

    respuesta = input(
        "> "
    ).strip()

    if respuesta == "":

        return sugerido

    return respuesta


# ============================================================
# PEDIR SUBCATEGORÍA
# ============================================================

def pedir_subcategoria(
    sugerido,
):

    while True:

        print()

        print(
            "SUBCATEGORÍA"
        )

        if sugerido:

            print(
                (
                    "Enter = aceptar "
                    f"'{sugerido}'"
                )
            )

        print(
            (
                "Puedes escribir otra "
                "subcategoría."
            )
        )

        respuesta = input(
            "> "
        ).strip()

        if respuesta == "":

            if sugerido:
                return sugerido

            print()

            print(
                (
                    "⚠️ Escribe una subcategoría."
                )
            )

            continue

        return respuesta


# ============================================================
# CREAR FILA RESUELTA
# ============================================================

def crear_fila_resuelta(
    item,
    tipo_movimiento,
    concepto,
    subcategoria,
):

    fila = list(
        item[
            "fila"
        ]
    )

    # Columna 1
    fila[
        0
    ] = tipo_movimiento

    # Columna 6
    fila[
        5
    ] = concepto

    # Columna 8
    fila[
        7
    ] = subcategoria

    return fila


# ============================================================
# REVISAR UN MOVIMIENTO
# ============================================================

def revisar_un_movimiento(
    numero,
    item,
):

    sugerencia = (
        crear_sugerencia_revision(
            item
        )
    )

    mostrar_movimiento_revision(
        numero,
        item,
        sugerencia,
    )

    tipo_movimiento = (
        pedir_tipo_movimiento(
            sugerencia[
                "tipo_movimiento"
            ]
        )
    )

    if tipo_movimiento is None:

        return {
            "estado": "omitido",
            "item": item,
        }

    concepto = pedir_concepto(
        sugerencia[
            "concepto"
        ]
    )

    subcategoria = (
        pedir_subcategoria(
            sugerencia[
                "subcategoria"
            ]
        )
    )

    fila = crear_fila_resuelta(
        item,
        tipo_movimiento,
        concepto,
        subcategoria,
    )

    return {
        "estado": "preparado",
        "item": item,
        "fila": fila,
        "tipo_movimiento": (
            tipo_movimiento
        ),
        "concepto": concepto,
        "subcategoria": (
            subcategoria
        ),
        "sugerencia": (
            sugerencia
        ),
    }


# ============================================================
# REVISIÓN INTERACTIVA
# ============================================================

def revisar_movimientos(
    proteccion,
):

    pendientes = (
        proteccion.get(
            "requieren_revision",
            [],
        )
    )

    decisiones = []
    omitidos = []

    if not pendientes:

        print()

        print(
            (
                "✅ No hay movimientos "
                "pendientes de revisión."
            )
        )

        return {
            "decisiones": [],
            "omitidos": [],
        }

    print()

    print(
        "=== REVISIÓN ASISTIDA DE MOVIMIENTOS ==="
    )

    print()

    print(
        (
            "Movimientos pendientes: "
            f"{len(pendientes)}"
        )
    )

    print()

    print(
        (
            "Puedes cambiar el tipo de movimiento, "
            "el concepto y la subcategoría."
        )
    )

    print(
        (
            "Nada será escrito hasta terminar "
            "la revisión y, en modo aplicar, "
            "confirmar explícitamente."
        )
    )

    for numero, item in enumerate(
        pendientes,
        start=1,
    ):

        resultado = revisar_un_movimiento(
            numero,
            item,
        )

        if resultado[
            "estado"
        ] == "omitido":

            omitidos.append(
                resultado[
                    "item"
                ]
            )

            print()

            print(
                "⏭️ Movimiento omitido."
            )

            continue

        decisiones.append(
            resultado
        )

        print()

        print(
            "✅ MOVIMIENTO PREPARADO"
        )

        print(
            (
                "Tipo: "
                f"{resultado['tipo_movimiento']}"
            )
        )

        print(
            (
                "Concepto: "
                f"{resultado['concepto']}"
            )
        )

        print(
            (
                "Subcategoría: "
                f"{resultado['subcategoria']}"
            )
        )

    return {
        "decisiones": decisiones,
        "omitidos": omitidos,
    }


# ============================================================
# MOSTRAR RESUMEN
# ============================================================

def mostrar_resumen_decisiones(
    revision,
):

    decisiones = revision[
        "decisiones"
    ]

    omitidos = revision[
        "omitidos"
    ]

    separador()

    print(
        "=== RESUMEN DE REVISIÓN ==="
    )

    print()

    print(
        (
            "Preparados: "
            f"{len(decisiones)}"
        )
    )

    print(
        (
            "Omitidos: "
            f"{len(omitidos)}"
        )
    )

    if decisiones:

        print()

        print(
            "MOVIMIENTOS PREPARADOS"
        )

        print(
            "-" * 60
        )

        for numero, decision in enumerate(
            decisiones,
            start=1,
        ):

            fila = decision[
                "fila"
            ]

            print()

            print(
                (
                    f"{numero:02d}. "
                    f"${float(fila[3]):,.2f}"
                    f" | "
                    f"{fila[6]}"
                )
            )

            print(
                (
                    "    Tipo: "
                    f"{fila[0]}"
                )
            )

            print(
                (
                    "    Concepto: "
                    f"{fila[5]}"
                )
            )

            print(
                (
                    "    Subcategoría: "
                    f"{fila[7]}"
                )
            )

    if omitidos:

        print()

        print(
            "MOVIMIENTOS OMITIDOS"
        )

        print(
            "-" * 60
        )

        for item in omitidos:

            fila = item[
                "fila"
            ]

            print(
                (
                    f"${float(fila[3]):,.2f}"
                    f" | "
                    f"{fila[6]}"
                )
            )


# ============================================================
# MOSTRAR MOVIMIENTOS SOLO EN SHEETS
# ============================================================

def mostrar_solo_sheets(
    conciliacion,
):

    pendientes = conciliacion.get(
        "solo_interno",
        [],
    )

    print()

    print(
        "=== MOVIMIENTOS SOLO EN SHEETS ==="
    )

    print()

    if not pendientes:

        print(
            (
                "✅ No hay movimientos "
                "sobrantes en Sheets."
            )
        )

        return

    print(
        (
            "Estos movimientos existen "
            "en Sheets pero no aparecen "
            "en el estado bancario."
        )
    )

    print()

    print(
        (
            "No serán borrados ni modificados "
            "automáticamente."
        )
    )

    for numero, interno in enumerate(
        pendientes,
        start=1,
    ):

        original = interno.get(
            "movimiento",
            {},
        )

        print()

        print(
            "-" * 60
        )

        print(
            (
                f"{numero:02d}. "
                f"${float(interno['monto']):,.2f}"
            )
        )

        print(
            (
                "Tipo movimiento: "
                f"{limpiar_texto(original.get('Tipo de Movimiento'))}"
            )
        )

        print(
            (
                "Concepto: "
                f"{limpiar_texto(original.get('Concepto'))}"
            )
        )

        print(
            (
                "Descripción: "
                f"{limpiar_texto(original.get('Descripcion'))}"
            )
        )

        print(
            (
                "Subcategoría: "
                f"{limpiar_texto(original.get('Subcategoria'))}"
            )
        )

        print(
            (
                "Fecha pago: "
                f"{limpiar_texto(original.get('Fecha de Pago'))}"
            )
        )

        print(
            (
                "Fecha compra: "
                f"{limpiar_texto(original.get('Fecha de Compra'))}"
            )
        )

        print(
            (
                "Cuenta: "
                f"{limpiar_texto(original.get('Cuenta'))}"
            )
        )

        print(
            (
                "Tipo pago: "
                f"{limpiar_texto(original.get('Tipo de Pago'))}"
            )
        )

        print(
            (
                "Número de plazos: "
                f"{limpiar_texto(original.get('Numero de Plazos'))}"
            )
        )

        print(
            (
                "Status: "
                f"{limpiar_texto(original.get('Status'))}"
            )
        )

    print()

    print(
        (
            "⚠️ Los movimientos Solo Sheets "
            "se diagnostican por separado."
        )
    )


# ============================================================
# PREVALIDAR DECISIONES
# ============================================================

def prevalidar_decisiones(
    revision,
):

    decisiones = revision[
        "decisiones"
    ]

    movimientos_actuales = (
        obtener_movimientos()
    )

    nuevas = []
    duplicadas = []
    conflictos = []

    for decision in decisiones:

        item_revision = {
            "fila": decision[
                "fila"
            ],
        }

        resultado = (
            revisar_cargo_regular_existente(
                item_revision,
                movimientos_actuales,
            )
        )

        estado = resultado[
            "estado"
        ]

        if estado == "nuevo":

            nuevas.append(
                decision
            )

        elif estado == "duplicado":

            duplicadas.append(
                {
                    "decision": decision,
                    "resultado": resultado,
                }
            )

        else:

            conflictos.append(
                {
                    "decision": decision,
                    "resultado": resultado,
                }
            )

    return {
        "nuevas": nuevas,
        "duplicadas": duplicadas,
        "conflictos": conflictos,
    }


# ============================================================
# MOSTRAR PREVALIDACIÓN
# ============================================================

def mostrar_prevalidacion(
    prevalidacion,
):

    separador()

    print(
        "=== PREVALIDACIÓN FINAL ==="
    )

    print()

    print(
        (
            "Nuevos seguros: "
            f"{len(prevalidacion['nuevas'])}"
        )
    )

    print(
        (
            "Ya existentes: "
            f"{len(prevalidacion['duplicadas'])}"
        )
    )

    print(
        (
            "Conflictos: "
            f"{len(prevalidacion['conflictos'])}"
        )
    )

    if prevalidacion[
        "conflictos"
    ]:

        print()

        print(
            "🛑 HAY CONFLICTOS"
        )

        print(
            (
                "No se escribirá ningún movimiento "
                "hasta resolverlos."
            )
        )


# ============================================================
# APLICAR DECISIONES
# ============================================================

def aplicar_decisiones(
    revision,
):

    prevalidacion = (
        prevalidar_decisiones(
            revision
        )
    )

    mostrar_prevalidacion(
        prevalidacion
    )

    if prevalidacion[
        "conflictos"
    ]:

        return {
            "agregadas": 0,
            "duplicadas": len(
                prevalidacion[
                    "duplicadas"
                ]
            ),
            "conflictos": len(
                prevalidacion[
                    "conflictos"
                ]
            ),
            "cancelado": True,
        }

    nuevas = prevalidacion[
        "nuevas"
    ]

    if not nuevas:

        print()

        print(
            (
                "✅ No hay movimientos nuevos "
                "que registrar."
            )
        )

        return {
            "agregadas": 0,
            "duplicadas": len(
                prevalidacion[
                    "duplicadas"
                ]
            ),
            "conflictos": 0,
            "cancelado": False,
        }

    print()

    print(
        "⚠️ MODO APLICAR"
    )

    print()

    print(
        (
            f"Se registrarán "
            f"{len(nuevas)} movimientos."
        )
    )

    print()

    print(
        (
            "Para confirmar escribe "
            "exactamente:"
        )
    )

    print()

    print(
        "APLICAR"
    )

    print()

    confirmacion = input(
        "> "
    ).strip()

    if confirmacion != "APLICAR":

        print()

        print(
            "🛑 Operación cancelada."
        )

        return {
            "agregadas": 0,
            "duplicadas": len(
                prevalidacion[
                    "duplicadas"
                ]
            ),
            "conflictos": 0,
            "cancelado": True,
        }

    # ========================================================
    # TERCERA LECTURA JUSTO ANTES DE ESCRIBIR
    # ========================================================

    movimientos_finales = (
        obtener_movimientos()
    )

    filas_finales = []
    duplicadas_finales = []
    conflictos_finales = []

    for decision in nuevas:

        item_revision = {
            "fila": decision[
                "fila"
            ],
        }

        resultado = (
            revisar_cargo_regular_existente(
                item_revision,
                movimientos_finales,
            )
        )

        estado = resultado[
            "estado"
        ]

        if estado == "nuevo":

            filas_finales.append(
                decision[
                    "fila"
                ]
            )

        elif estado == "duplicado":

            duplicadas_finales.append(
                decision
            )

        else:

            conflictos_finales.append(
                {
                    "decision": decision,
                    "resultado": resultado,
                }
            )

    if conflictos_finales:

        print()

        print(
            "🛑 OPERACIÓN CANCELADA"
        )

        print(
            (
                "Apareció un conflicto durante "
                "la validación final."
            )
        )

        print()

        print(
            (
                "No se escribió ningún movimiento."
            )
        )

        return {
            "agregadas": 0,
            "duplicadas": (
                len(
                    prevalidacion[
                        "duplicadas"
                    ]
                )
                +
                len(
                    duplicadas_finales
                )
            ),
            "conflictos": len(
                conflictos_finales
            ),
            "cancelado": True,
        }

    if not filas_finales:

        print()

        print(
            (
                "✅ Todos los movimientos "
                "ya existían."
            )
        )

        return {
            "agregadas": 0,
            "duplicadas": (
                len(
                    prevalidacion[
                        "duplicadas"
                    ]
                )
                +
                len(
                    duplicadas_finales
                )
            ),
            "conflictos": 0,
            "cancelado": False,
        }

    registrar_movimientos(
        filas_finales
    )

    monto_total = sum(
        float(
            fila[
                3
            ]
        )
        for fila
        in filas_finales
    )

    print()

    print(
        "✅ MOVIMIENTOS REGISTRADOS"
    )

    print()

    print(
        (
            "Filas agregadas: "
            f"{len(filas_finales)}"
        )
    )

    print(
        (
            "Monto agregado: "
            f"${monto_total:,.2f}"
        )
    )

    return {
        "agregadas": len(
            filas_finales
        ),
        "duplicadas": (
            len(
                prevalidacion[
                    "duplicadas"
                ]
            )
            +
            len(
                duplicadas_finales
            )
        ),
        "conflictos": 0,
        "cancelado": False,
    }


# ============================================================
# ANALIZAR ESTADO
# ============================================================

def analizar_estado(
    ruta_pdf,
):

    print()

    print(
        "📄 Leyendo estado..."
    )

    datos = extraer_datos_estado(
        ruta_pdf
    )

    texto = extraer_texto_pdf(
        ruta_pdf
    )

    resumen = (
        extraer_resumen_cargos_abonos(
            texto
        )
    )

    movimientos_banco = (
        extraer_movimientos_regulares_invex(
            texto
        )
    )

    cuenta = datos.get(
        "cuenta"
    )

    periodo = datos.get(
        "periodo"
    )

    print()

    print(
        (
            "Cuenta: "
            f"{cuenta}"
        )
    )

    print(
        (
            "Periodo: "
            f"{periodo}"
        )
    )

    validacion = validar_estado(
        datos,
        resumen,
        movimientos_banco,
    )

    print()

    print(
        "=== VALIDACIÓN DEL ESTADO ==="
    )

    print()

    if not validacion[
        "valido"
    ]:

        print(
            "❌ EL ESTADO NO CUADRA"
        )

        print(
            validacion.get(
                "error",
                "Validación fallida.",
            )
        )

        return None

    print(
        "✅ EL ESTADO CUADRA"
    )

    print(
        (
            "Calculado: "
            f"${validacion['calculado']:,.2f}"
        )
    )

    print(
        (
            "Pago estado: "
            f"${validacion['pago_estado']:,.2f}"
        )
    )

    conciliacion = (
        conciliar_con_sheets(
            datos,
            movimientos_banco,
        )
    )

    print()

    print(
        "=== CONCILIACIÓN ACTUAL ==="
    )

    print()

    print(
        (
            "Coincidencias: "
            f"{len(conciliacion['coincidencias'])}"
        )
    )

    print(
        (
            "Solo banco: "
            f"{len(conciliacion['solo_banco'])}"
        )
    )

    print(
        (
            "Solo Sheets: "
            f"{len(conciliacion['solo_interno'])}"
        )
    )

    analisis_msi = (
        mostrar_analisis_msi_bbva(
            datos,
            texto,
        )
    )

    analisis_regulares = (
        preparar_cargos_regulares_faltantes(
            datos,
            conciliacion,
            analisis_msi,
        )
    )

    (
        analisis_cuotas,
        conciliacion,
    ) = conciliar_cuotas_genericas(
        datos,
        conciliacion,
        analisis_regulares,
        mostrar=False,
    )

    proteccion = (
        analizar_proteccion_regulares(
            analisis_regulares
        )
    )

    return {
        "datos": datos,
        "texto": texto,
        "resumen": resumen,
        "movimientos_banco": (
            movimientos_banco
        ),
        "conciliacion": conciliacion,
        "analisis_msi": analisis_msi,
        "analisis_regulares": (
            analisis_regulares
        ),
        "analisis_cuotas": (
            analisis_cuotas
        ),
        "proteccion": proteccion,
    }


# ============================================================
# RESULTADO FINAL
# ============================================================

def mostrar_resultado_final(
    analisis,
):

    datos = analisis[
        "datos"
    ]

    movimientos_banco = analisis[
        "movimientos_banco"
    ]

    conciliacion = (
        conciliar_con_sheets(
            datos,
            movimientos_banco,
        )
    )

    print()

    print(
        "=== CONCILIACIÓN DESPUÉS DE LA REVISIÓN ==="
    )

    print()

    print(
        (
            "Coincidencias: "
            f"{len(conciliacion['coincidencias'])}"
        )
    )

    print(
        (
            "Solo banco: "
            f"{len(conciliacion['solo_banco'])}"
        )
    )

    print(
        (
            "Solo Sheets: "
            f"{len(conciliacion['solo_interno'])}"
        )
    )

    monto_coincidente = sum(
        float(
            item[
                "banco"
            ][
                "monto"
            ]
        )
        for item
        in conciliacion[
            "coincidencias"
        ]
    )

    monto_solo_banco = sum(
        float(
            item[
                "monto"
            ]
        )
        for item
        in conciliacion[
            "solo_banco"
        ]
    )

    monto_solo_sheets = sum(
        float(
            item[
                "monto"
            ]
        )
        for item
        in conciliacion[
            "solo_interno"
        ]
    )

    print()

    print(
        (
            "Monto coincidente: "
            f"${monto_coincidente:,.2f}"
        )
    )

    print(
        (
            "Solo banco: "
            f"${monto_solo_banco:,.2f}"
        )
    )

    print(
        (
            "Solo Sheets: "
            f"${monto_solo_sheets:,.2f}"
        )
    )

    mostrar_solo_sheets(
        conciliacion
    )


# ============================================================
# MAIN
# ============================================================

def main():

    argumentos = sys.argv[
        1:
    ]

    aplicar = (
        "--aplicar"
        in argumentos
    )

    rutas = [
        argumento
        for argumento
        in argumentos
        if not argumento.startswith(
            "--"
        )
    ]

    if len(
        rutas
    ) != 1:

        print()

        print(
            "Uso:"
        )

        print()

        print(
            (
                "python revisar_estado.py "
                "\"estados/archivo.pdf\""
            )
        )

        print()

        print(
            (
                "python revisar_estado.py "
                "\"estados/archivo.pdf\" "
                "--aplicar"
            )
        )

        return

    ruta_pdf = rutas[
        0
    ]

    print()

    if aplicar:

        print(
            (
                "🔧 REVISIÓN ASISTIDA "
                "EN MODO APLICAR"
            )
        )

    else:

        print(
            (
                "🔍 REVISIÓN ASISTIDA "
                "EN MODO SIMULACIÓN"
            )
        )

        print()

        print(
            (
                "Tus respuestas se mostrarán, "
                "pero Google Sheets "
                "NO será modificado."
            )
        )

    analisis = analizar_estado(
        ruta_pdf
    )

    if analisis is None:
        return

    proteccion = analisis[
        "proteccion"
    ]

    print()

    print(
        "=== ESTADO DE LA REVISIÓN ==="
    )

    print()

    print(
        (
            "Autoimportables pendientes: "
            f"{len(proteccion['autoimportables'])}"
        )
    )

    print(
        (
            "Requieren revisión manual: "
            f"{len(proteccion['requieren_revision'])}"
        )
    )

    print(
        (
            "Conflictos estructurales: "
            f"{len(proteccion['conflictos'])}"
        )
    )

    revision = revisar_movimientos(
        proteccion
    )

    mostrar_resumen_decisiones(
        revision
    )

    mostrar_solo_sheets(
        analisis[
            "conciliacion"
        ]
    )

    if not aplicar:

        print()

        print(
            "🔍 FIN DE SIMULACIÓN"
        )

        print()

        print(
            (
                "Google Sheets "
                "NO fue modificado."
            )
        )

        print()

        print(
            (
                "No ejecutes todavía "
                "con --aplicar."
            )
        )

        return

    resultado = aplicar_decisiones(
        revision
    )

    if resultado[
        "cancelado"
    ]:

        print()

        print(
            (
                "No se continuará con "
                "la conciliación final."
            )
        )

        return

    mostrar_resultado_final(
        analisis
    )


if __name__ == "__main__":
    main()