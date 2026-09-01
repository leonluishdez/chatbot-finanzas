import sys
from datetime import datetime

from lector_estados import (
    extraer_datos_estado,
    extraer_texto_pdf,
    extraer_resumen_cargos_abonos,
    extraer_movimientos_regulares_invex,
    extraer_planes_msi_bbva,
    clasificar_abonos_estado,
    sumar_movimientos,
)

from sheets import (
    obtener_movimientos,
    obtener_estados_cuenta,
    registrar_estado_cuenta,
    registrar_movimientos,
    obtener_hoja_estados_cuenta,
)

from finanzas import (
    convertir_fecha,
    convertir_monto,
    generar_cuotas,
    normalizar_texto,
    obtener_movimientos_fecha_pago,
)

from conciliar_movimientos import (
    preparar_movimientos_internos,
    comparar_movimientos,
)


# ============================================================
# MESES
# ============================================================

MESES_BANCO = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}


# ============================================================
# ABONOS APLICABLES
# ============================================================

def calcular_abonos_aplicables(
    cuenta,
    pagos_reales,
    aclaraciones,
    devoluciones,
    otros_abonos,
):

    if cuenta == "Invex":

        return round(
            pagos_reales,
            2,
        )

    if cuenta in (
        "Citibanamex Costco",
        "Citibanamex Oro",
        "BBVA Platinum",
    ):

        return round(
            pagos_reales
            + aclaraciones
            + devoluciones
            + otros_abonos,
            2,
        )

    return round(
        pagos_reales,
        2,
    )


# ============================================================
# BUSCAR ESTADO EXISTENTE
# ============================================================

def buscar_estado_existente(
    estados,
    cuenta,
    periodo,
):

    cuenta_objetivo = str(
        cuenta
    ).strip().lower()

    periodo_objetivo = str(
        periodo
    ).strip().lower()

    for estado in estados:

        cuenta_estado = str(
            estado.get(
                "Cuenta",
                "",
            )
        ).strip().lower()

        periodo_estado = str(
            estado.get(
                "Periodo",
                "",
            )
        ).strip().lower()

        if (
            cuenta_estado == cuenta_objetivo
            and periodo_estado == periodo_objetivo
        ):

            return estado

    return None


# ============================================================
# ACTUALIZAR ESTADO
# ============================================================

def actualizar_estado_existente(
    cuenta,
    periodo,
    status,
):

    hoja = obtener_hoja_estados_cuenta()

    valores = hoja.get_all_values()

    if not valores:

        raise RuntimeError(
            "La hoja EstadosCuenta está vacía."
        )

    encabezados = valores[0]

    columnas = {
        nombre: indice
        for indice, nombre
        in enumerate(encabezados)
    }

    requeridas = [
        "Cuenta",
        "Periodo",
        "Status",
    ]

    faltantes = [
        columna
        for columna in requeridas
        if columna not in columnas
    ]

    if faltantes:

        raise RuntimeError(
            (
                "Faltan columnas en EstadosCuenta: "
                + ", ".join(
                    faltantes
                )
            )
        )

    coincidencias = []

    cuenta_objetivo = str(
        cuenta
    ).strip().lower()

    periodo_objetivo = str(
        periodo
    ).strip().lower()

    for numero_fila, fila in enumerate(
        valores[1:],
        start=2,
    ):

        indice_maximo = max(
            columnas["Cuenta"],
            columnas["Periodo"],
            columnas["Status"],
        )

        if len(fila) <= indice_maximo:

            continue

        cuenta_fila = str(
            fila[
                columnas["Cuenta"]
            ]
        ).strip().lower()

        periodo_fila = str(
            fila[
                columnas["Periodo"]
            ]
        ).strip().lower()

        if (
            cuenta_fila == cuenta_objetivo
            and periodo_fila == periodo_objetivo
        ):

            coincidencias.append(
                numero_fila
            )

    if not coincidencias:

        return False

    if len(coincidencias) > 1:

        raise RuntimeError(
            (
                "Hay más de un estado para "
                f"{cuenta} | {periodo}. "
                "No se modificó nada."
            )
        )

    fila = coincidencias[0]

    columna_status = (
        columnas["Status"] + 1
    )

    status_actual = hoja.cell(
        fila,
        columna_status,
    ).value

    if status_actual == status:

        print(
            f"Status ya correcto: {status}"
        )

        return True

    hoja.update_cell(
        fila,
        columna_status,
        status,
    )

    print(
        (
            "Status actualizado: "
            f"{status_actual} → {status}"
        )
    )

    return True


# ============================================================
# VALIDAR ESTADO
# ============================================================

def validar_estado(
    datos,
    resumen,
    movimientos_banco,
):

    cuenta = datos.get(
        "cuenta"
    )

    componentes = {
        "adeudo_anterior": resumen.get(
            "adeudo_anterior"
        ),
        "cargos_regulares": resumen.get(
            "cargos_regulares"
        ),
        "cargos_meses": resumen.get(
            "cargos_meses"
        ),
        "intereses": resumen.get(
            "intereses"
        ),
        "comisiones": resumen.get(
            "comisiones"
        ),
        "iva": resumen.get(
            "iva"
        ),
        "pagos_abonos": resumen.get(
            "pagos_abonos"
        ),
    }

    faltantes = [
        nombre
        for nombre, valor
        in componentes.items()
        if valor is None
    ]

    if faltantes:

        return {
            "valido": False,
            "error": (
                "Faltan componentes del estado: "
                + ", ".join(
                    faltantes
                )
            ),
        }

    abonos = clasificar_abonos_estado(
        movimientos_banco,
        cuenta,
    )

    pagos_reales = sumar_movimientos(
        abonos.get(
            "pagos_reales",
            [],
        )
    )

    aclaraciones = sumar_movimientos(
        abonos.get(
            "aclaraciones",
            [],
        )
    )

    devoluciones = sumar_movimientos(
        abonos.get(
            "devoluciones",
            [],
        )
    )

    otros_abonos = sumar_movimientos(
        abonos.get(
            "otros_abonos",
            [],
        )
    )

    total_clasificado = round(
        pagos_reales
        + aclaraciones
        + devoluciones
        + otros_abonos,
        2,
    )

    pagos_abonos_banco = resumen[
        "pagos_abonos"
    ]

    diferencia_abonos = round(
        pagos_abonos_banco
        - total_clasificado,
        2,
    )

    if abs(diferencia_abonos) > 0.01:

        return {
            "valido": False,
            "error": (
                "Los abonos no están "
                "completamente clasificados."
            ),
            "diferencia_abonos": (
                diferencia_abonos
            ),
        }

    abonos_aplicables = (
        calcular_abonos_aplicables(
            cuenta,
            pagos_reales,
            aclaraciones,
            devoluciones,
            otros_abonos,
        )
    )

    calculado = round(
        resumen["adeudo_anterior"]
        + resumen["cargos_regulares"]
        + resumen["cargos_meses"]
        + resumen["intereses"]
        + resumen["comisiones"]
        + resumen["iva"]
        - abonos_aplicables,
        2,
    )

    pago_estado = resumen.get(
        "pago_no_intereses"
    )

    if pago_estado is None:

        pago_estado = datos.get(
            "pago_para_no_generar_intereses"
        )

    if pago_estado is None:

        return {
            "valido": False,
            "error": (
                "No pude obtener el pago "
                "para no generar intereses."
            ),
        }

    diferencia = round(
        pago_estado
        - calculado,
        2,
    )

    return {
        "valido": (
            abs(diferencia) <= 0.01
        ),
        "calculado": calculado,
        "pago_estado": pago_estado,
        "diferencia": diferencia,
        "pagos_reales": pagos_reales,
        "aclaraciones": aclaraciones,
        "devoluciones": devoluciones,
        "otros_abonos": otros_abonos,
        "abonos_aplicables": (
            abonos_aplicables
        ),
    }


# ============================================================
# CONCILIAR CONTRA SHEETS
# ============================================================

def conciliar_con_sheets(
    datos,
    movimientos_banco,
):

    cuenta = datos[
        "cuenta"
    ]

    fecha_limite = datos[
        "fecha_limite_pago"
    ]

    todos_movimientos = (
        obtener_movimientos()
    )

    fecha_limite_objeto = (
        convertir_fecha(
            fecha_limite
        )
    )

    movimientos_periodo = (
        obtener_movimientos_fecha_pago(
            todos_movimientos,
            cuenta,
            fecha_limite_objeto,
        )
    )

    movimientos_internos = (
        preparar_movimientos_internos(
            movimientos_periodo
        )
    )

    resultado = comparar_movimientos(
        movimientos_banco,
        movimientos_internos,
    )

    coincidencias = resultado[
        "coincidencias"
    ]

    solo_banco = resultado[
        "solo_banco"
    ]

    solo_interno = resultado[
        "solo_interno"
    ]

    total_coincidente = round(
        sum(
            item["banco"]["monto"]
            for item
            in coincidencias
        ),
        2,
    )

    total_solo_banco = round(
        sum(
            movimiento["monto"]
            for movimiento
            in solo_banco
        ),
        2,
    )

    total_solo_interno = round(
        sum(
            movimiento["monto"]
            for movimiento
            in solo_interno
        ),
        2,
    )

    conciliado = (
        len(solo_banco) == 0
        and len(solo_interno) == 0
    )

    return {
        "conciliado": conciliado,
        "coincidencias": coincidencias,
        "solo_banco": solo_banco,
        "solo_interno": solo_interno,
        "total_coincidente": (
            total_coincidente
        ),
        "total_solo_banco": (
            total_solo_banco
        ),
        "total_solo_interno": (
            total_solo_interno
        ),
    }


# ============================================================
# MOSTRAR RESUMEN DE CONCILIACIÓN
# ============================================================

def mostrar_resumen_conciliacion(
    conciliacion,
):

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


# ============================================================
# FECHA MSI BBVA
# ============================================================

def convertir_fecha_plan_bbva(
    valor,
):

    if isinstance(
        valor,
        datetime,
    ):

        return valor

    texto = str(
        valor
    ).strip().lower()

    partes = texto.split(
        "-"
    )

    if len(partes) != 3:

        raise ValueError(
            (
                "Fecha de compra MSI "
                f"no reconocida: {valor}"
            )
        )

    dia = int(
        partes[0]
    )

    mes_texto = partes[
        1
    ][:3]

    if mes_texto not in MESES_BANCO:

        raise ValueError(
            (
                "Mes MSI no reconocido: "
                f"{partes[1]}"
            )
        )

    mes = MESES_BANCO[
        mes_texto
    ]

    anio = int(
        partes[2]
    )

    if anio < 100:

        anio += 2000

    return datetime(
        anio,
        mes,
        dia,
    )


# ============================================================
# DETECTAR PLANES MSI
# ============================================================

def detectar_planes_msi_bbva(
    datos,
    texto,
):

    cuenta = datos.get(
        "cuenta"
    )

    if cuenta != "BBVA Platinum":

        return {
            "aplica": False,
            "planes": [],
            "encontrados": [],
            "faltantes": [],
        }

    planes = extraer_planes_msi_bbva(
        texto
    )

    todos_movimientos = (
        obtener_movimientos()
    )

    fecha_limite = convertir_fecha(
        datos[
            "fecha_limite_pago"
        ]
    )

    movimientos_periodo = (
        obtener_movimientos_fecha_pago(
            todos_movimientos,
            cuenta,
            fecha_limite,
        )
    )

    encontrados = []
    faltantes = []
    indices_usados = set()

    for plan in planes:

        encontrado = None

        for indice, movimiento in enumerate(
            movimientos_periodo
        ):

            if indice in indices_usados:

                continue

            tipo_pago = str(
                movimiento.get(
                    "Tipo de Pago",
                    "",
                )
            ).strip().lower()

            if tipo_pago != "meses":

                continue

            try:

                numero_plazos = int(
                    float(
                        str(
                            movimiento.get(
                                "Numero de Plazos",
                                0,
                            )
                        )
                    )
                )

            except (
                ValueError,
                TypeError,
            ):

                continue

            if (
                numero_plazos
                != plan["plazos"]
            ):

                continue

            try:

                monto = convertir_monto(
                    movimiento.get(
                        "Monto de Compra",
                        0,
                    )
                )

            except (
                ValueError,
                TypeError,
            ):

                continue

            if abs(
                monto
                - plan["cuota"]
            ) > 0.01:

                continue

            encontrado = {
                "plan": plan,
                "movimiento": movimiento,
            }

            indices_usados.add(
                indice
            )

            break

        if encontrado:

            encontrados.append(
                encontrado
            )

        else:

            faltantes.append(
                plan
            )

    return {
        "aplica": True,
        "planes": planes,
        "encontrados": encontrados,
        "faltantes": faltantes,
    }


# ============================================================
# VALIDAR RECONSTRUCCIÓN MSI
# ============================================================

def validar_reconstruccion_msi_bbva(
    analisis_msi,
    cuenta,
):

    if not analisis_msi[
        "aplica"
    ]:

        return {
            "aplica": False,
            "resultados": [],
            "validos": [],
            "invalidos": [],
        }

    resultados = []
    validos = []
    invalidos = []

    planes_faltantes_ids = {
        (
            plan["monto_original"],
            plan["plazos"],
            plan["numero"],
            plan["cuota"],
            plan["descripcion"],
        )
        for plan
        in analisis_msi[
            "faltantes"
        ]
    }

    for plan in analisis_msi[
        "planes"
    ]:

        fecha_compra = (
            convertir_fecha_plan_bbva(
                plan[
                    "fecha_compra"
                ]
            )
        )

        cuotas = generar_cuotas(
            plan["monto_original"],
            plan["plazos"],
            fecha_compra,
            plan["descripcion"],
            cuenta,
        )

        cuota_actual = None

        for cuota in cuotas:

            if (
                cuota["numero"]
                == plan["numero"]
            ):

                cuota_actual = cuota

                break

        identidad = (
            plan["monto_original"],
            plan["plazos"],
            plan["numero"],
            plan["cuota"],
            plan["descripcion"],
        )

        faltante = (
            identidad
            in planes_faltantes_ids
        )

        if cuota_actual is None:

            resultado = {
                "plan": plan,
                "cuotas": cuotas,
                "valido": False,
                "error": (
                    "No se encontró "
                    "la cuota actual."
                ),
                "faltante": faltante,
            }

            resultados.append(
                resultado
            )

            invalidos.append(
                resultado
            )

            continue

        total_reconstruido = round(
            sum(
                cuota["monto"]
                for cuota
                in cuotas
            ),
            2,
        )

        diferencia_total = round(
            total_reconstruido
            - plan["monto_original"],
            2,
        )

        diferencia_cuota = round(
            cuota_actual["monto"]
            - plan["cuota"],
            2,
        )

        valido = (
            abs(diferencia_total) <= 0.01
            and
            abs(diferencia_cuota) <= 0.01
        )

        resultado = {
            "plan": plan,
            "cuotas": cuotas,
            "cuota_actual": cuota_actual,
            "total_reconstruido": (
                total_reconstruido
            ),
            "diferencia_total": (
                diferencia_total
            ),
            "diferencia_cuota": (
                diferencia_cuota
            ),
            "valido": valido,
            "faltante": faltante,
        }

        resultados.append(
            resultado
        )

        if valido:

            validos.append(
                resultado
            )

        else:

            invalidos.append(
                resultado
            )

    return {
        "aplica": True,
        "resultados": resultados,
        "validos": validos,
        "invalidos": invalidos,
    }


# ============================================================
# PREPARAR FILAS MSI
# ============================================================

def preparar_filas_msi_faltantes_bbva(
    analisis_msi,
):

    filas = []

    validacion = analisis_msi.get(
        "validacion"
    )

    if not validacion:

        return filas

    for resultado in validacion[
        "validos"
    ]:

        if not resultado[
            "faltante"
        ]:

            continue

        plan = resultado[
            "plan"
        ]

        fecha_compra = (
            convertir_fecha_plan_bbva(
                plan[
                    "fecha_compra"
                ]
            )
        )

        descripcion_base = str(
            plan[
                "descripcion"
            ]
        ).split(
            ";"
        )[0].strip()

        for cuota in resultado[
            "cuotas"
        ]:

            numero = cuota[
                "numero"
            ]

            plazos = plan[
                "plazos"
            ]

            descripcion = (
                f"{descripcion_base} "
                f"{numero} de {plazos}"
            )

            if numero < plan[
                "numero"
            ]:

                status = "Pagado"

            else:

                status = "Pendiente"

            fila = [
                "Gasto",
                cuota[
                    "fecha"
                ].strftime(
                    "%d/%m/%Y"
                ),
                fecha_compra.strftime(
                    "%d/%m/%Y"
                ),
                cuota[
                    "monto"
                ],
                "BBVA Platinum",
                "",
                descripcion,
                "Varios",
                "Meses",
                plazos,
                status,
            ]

            filas.append(
                {
                    "fila": fila,
                    "plan": plan,
                    "cuota": cuota,
                    "descripcion": descripcion,
                }
            )

    return filas


# ============================================================
# REVISAR CUOTA MSI
# ============================================================

def revisar_cuota_msi_existente(
    fila_propuesta,
    movimientos,
):

    fecha_propuesta = convertir_fecha(
        fila_propuesta[
            1
        ]
    )

    monto_propuesto = float(
        fila_propuesta[
            3
        ]
    )

    cuenta_propuesta = str(
        fila_propuesta[
            4
        ]
    ).strip().lower()

    tipo_pago_propuesto = str(
        fila_propuesta[
            8
        ]
    ).strip().lower()

    plazos_propuestos = int(
        fila_propuesta[
            9
        ]
    )

    coincidencias = []

    for movimiento in movimientos:

        cuenta = str(
            movimiento.get(
                "Cuenta",
                "",
            )
        ).strip().lower()

        if cuenta != cuenta_propuesta:

            continue

        tipo_pago = str(
            movimiento.get(
                "Tipo de Pago",
                "",
            )
        ).strip().lower()

        if tipo_pago != tipo_pago_propuesto:

            continue

        try:

            plazos = int(
                float(
                    str(
                        movimiento.get(
                            "Numero de Plazos",
                            0,
                        )
                    )
                )
            )

        except (
            ValueError,
            TypeError,
        ):

            continue

        if plazos != plazos_propuestos:

            continue

        try:

            monto = convertir_monto(
                movimiento.get(
                    "Monto de Compra",
                    0,
                )
            )

        except Exception:

            continue

        if abs(
            monto
            - monto_propuesto
        ) > 0.01:

            continue

        try:

            fecha = convertir_fecha(
                movimiento.get(
                    "Fecha de Pago",
                    "",
                )
            )

        except Exception:

            continue

        if (
            fecha.year
            != fecha_propuesta.year
            or fecha.month
            != fecha_propuesta.month
            or fecha.day
            != fecha_propuesta.day
        ):

            continue

        coincidencias.append(
            movimiento
        )

    if len(coincidencias) == 0:

        return {
            "estado": "nuevo",
        }

    if len(coincidencias) == 1:

        return {
            "estado": "duplicado",
            "movimiento": (
                coincidencias[0]
            ),
        }

    return {
        "estado": "conflicto",
        "movimientos": coincidencias,
    }


# ============================================================
# APLICAR MSI
# ============================================================

def aplicar_msi_faltantes_bbva(
    analisis_msi,
):

    filas_propuestas = (
        analisis_msi.get(
            "filas_propuestas",
            [],
        )
    )

    if not filas_propuestas:

        print()

        print(
            "✅ No hay MSI nuevos por registrar."
        )

        return {
            "agregadas": 0,
            "duplicadas": 0,
            "conflictos": 0,
        }

    movimientos = obtener_movimientos()

    nuevas = []
    duplicadas = []
    conflictos = []

    for item in filas_propuestas:

        revision = (
            revisar_cuota_msi_existente(
                item["fila"],
                movimientos,
            )
        )

        estado = revision[
            "estado"
        ]

        if estado == "duplicado":

            duplicadas.append(
                item
            )

        elif estado == "conflicto":

            conflictos.append(
                {
                    "item": item,
                    "revision": revision,
                }
            )

        else:

            nuevas.append(
                item
            )

    print()

    print(
        "=== PROTECCIÓN CONTRA DUPLICADOS MSI ==="
    )

    print()

    print(
        f"Filas propuestas: {len(filas_propuestas)}"
    )

    print(
        f"Ya existentes: {len(duplicadas)}"
    )

    print(
        f"Conflictos: {len(conflictos)}"
    )

    print(
        f"Nuevas: {len(nuevas)}"
    )

    if conflictos:

        print()

        print(
            "⚠️ Hay conflictos MSI."
        )

        print(
            (
                "Las filas conflictivas "
                "NO serán registradas."
            )
        )

    if not nuevas:

        print()

        print(
            "✅ No hay filas MSI nuevas que escribir."
        )

        return {
            "agregadas": 0,
            "duplicadas": len(
                duplicadas
            ),
            "conflictos": len(
                conflictos
            ),
        }

    filas_sheets = [
        item[
            "fila"
        ]
        for item
        in nuevas
    ]

    registrar_movimientos(
        filas_sheets
    )

    print()

    print(
        "✅ MSI REGISTRADOS"
    )

    print(
        f"Filas agregadas: {len(filas_sheets)}"
    )

    return {
        "agregadas": len(
            filas_sheets
        ),
        "duplicadas": len(
            duplicadas
        ),
        "conflictos": len(
            conflictos
        ),
    }


# ============================================================
# MOSTRAR MSI
# ============================================================

def mostrar_analisis_msi_bbva(
    datos,
    texto,
):

    analisis_msi = (
        detectar_planes_msi_bbva(
            datos,
            texto,
        )
    )

    if not analisis_msi[
        "aplica"
    ]:

        return analisis_msi

    print()

    print(
        "=== PLANES MSI BBVA ==="
    )

    print()

    print(
        (
            "Planes detectados: "
            f"{len(analisis_msi['planes'])}"
        )
    )

    print(
        (
            "Ya existentes: "
            f"{len(analisis_msi['encontrados'])}"
        )
    )

    print(
        (
            "Planes faltantes: "
            f"{len(analisis_msi['faltantes'])}"
        )
    )

    if not analisis_msi[
        "faltantes"
    ]:

        print()

        print(
            (
                "✅ TODOS LOS PLANES MSI "
                "ESTÁN EN SHEETS"
            )
        )

    validacion = (
        validar_reconstruccion_msi_bbva(
            analisis_msi,
            datos[
                "cuenta"
            ],
        )
    )

    analisis_msi[
        "validacion"
    ] = validacion

    print()

    print(
        "=== VALIDACIÓN MATEMÁTICA MSI ==="
    )

    print()

    print(
        (
            "Planes reproducibles: "
            f"{len(validacion['validos'])}"
        )
    )

    print(
        (
            "Planes inconsistentes: "
            f"{len(validacion['invalidos'])}"
        )
    )

    for resultado in validacion[
        "resultados"
    ]:

        plan = resultado[
            "plan"
        ]

        print()

        marca = (
            "✅"
            if resultado[
                "valido"
            ]
            else "❌"
        )

        print(
            (
                f"{marca} "
                f"{plan['numero']:02d}/"
                f"{plan['plazos']:02d}"
                f" | "
                f"${plan['cuota']:,.2f}"
                f" | original "
                f"${plan['monto_original']:,.2f}"
            )
        )

        print(
            (
                "   "
                f"{plan['descripcion']}"
            )
        )

        if resultado[
            "valido"
        ]:

            print(
                (
                    "   Reconstruido: "
                    f"${resultado['total_reconstruido']:,.2f}"
                )
            )

            print(
                (
                    "   Diferencia total: "
                    f"${resultado['diferencia_total']:,.2f}"
                )
            )

            print(
                (
                    "   Diferencia cuota: "
                    f"${resultado['diferencia_cuota']:,.2f}"
                )
            )

    filas_propuestas = (
        preparar_filas_msi_faltantes_bbva(
            analisis_msi
        )
    )

    analisis_msi[
        "filas_propuestas"
    ] = filas_propuestas

    print()

    print(
        "=== SIMULACIÓN DE ALTA MSI ==="
    )

    print()

    print(
        (
            "Filas MSI propuestas: "
            f"{len(filas_propuestas)}"
        )
    )

    if not filas_propuestas:

        print(
            "✅ No hay MSI faltantes por generar."
        )

    else:

        for item in filas_propuestas:

            cuota = item[
                "cuota"
            ]

            plan = item[
                "plan"
            ]

            print(
                (
                    f"{cuota['numero']:02d}/"
                    f"{plan['plazos']:02d}"
                    f" | "
                    f"{cuota['fecha'].strftime('%d/%m/%Y')}"
                    f" | "
                    f"${cuota['monto']:,.2f}"
                )
            )

    return analisis_msi


# ============================================================
# FECHA MOVIMIENTO BANCARIO
# ============================================================

def convertir_fecha_movimiento_banco(
    valor,
):

    try:

        return convertir_fecha(
            valor
        )

    except Exception:

        return convertir_fecha_plan_bbva(
            valor
        )


# ============================================================
# ¿MOVIMIENTO ES MSI?
# ============================================================

def movimiento_corresponde_a_msi_bbva(
    movimiento,
    analisis_msi,
):

    if not analisis_msi.get(
        "aplica",
        False,
    ):

        return False

    descripcion_banco = normalizar_texto(
        movimiento.get(
            "descripcion",
            "",
        )
    )

    try:

        monto_banco = float(
            movimiento.get(
                "monto",
                0,
            )
        )

    except (
        ValueError,
        TypeError,
    ):

        return False

    for plan in analisis_msi.get(
        "planes",
        [],
    ):

        if abs(
            monto_banco
            - plan["cuota"]
        ) > 0.01:

            continue

        descripcion_plan = str(
            plan.get(
                "descripcion",
                "",
            )
        )

        comercio_plan = (
            descripcion_plan
            .split(";")[0]
            .strip()
        )

        comercio_plan = normalizar_texto(
            comercio_plan
        )

        if not comercio_plan:

            continue

        if (
            comercio_plan
            in descripcion_banco
            or
            descripcion_banco
            in comercio_plan
        ):

            return True

    return False


# ============================================================
# CATEGORIZAR REGULAR
# ============================================================

def categorizar_cargo_regular(
    descripcion,
):

    texto = normalizar_texto(
        descripcion
    )

    reglas = [
        (
            "Comida",
            "Alta",
            [
                "didifood",
                "didi food",
                "city market",
                "oxxo",
                "abts",
                "restaurant",
                "rest ",
                "cafe",
                "walmart",
                "wal mart",
            ],
        ),
        (
            "Transporte",
            "Alta",
            [
                "uber",
                "super didi",
                "didi",
            ],
        ),
        (
            "Salud",
            "Alta",
            [
                "farm guadalajara",
                "farmacia",
                "farm ",
                "tda nat",
                "natu",
            ],
        ),
        (
            "Salud",
            "Media",
            [
                "sanrafael",
                "allianz",
            ],
        ),
        (
            "Entretenimiento",
            "Alta",
            [
                "cinepolis",
                "cinemex",
                "netflix",
            ],
        ),
        (
            "Servicios",
            "Alta",
            [
                "at t",
                "telcel",
                "totalplay",
                "izzi",
            ],
        ),
    ]

    for (
        categoria,
        confianza,
        palabras,
    ) in reglas:

        for regla in palabras:

            if regla in texto:

                return {
                    "categoria": categoria,
                    "confianza": confianza,
                    "regla": regla,
                }

    return {
        "categoria": "Varios",
        "confianza": "Baja",
        "regla": None,
    }


# ============================================================
# PREPARAR REGULARES FALTANTES
# ============================================================

def preparar_cargos_regulares_faltantes(
    datos,
    conciliacion,
    analisis_msi,
):

    cuenta = datos[
        "cuenta"
    ]

    fecha_limite = convertir_fecha(
        datos[
            "fecha_limite_pago"
        ]
    )

    propuestas = []
    msi_excluidos = []

    for movimiento in conciliacion[
        "solo_banco"
    ]:

        if (
            cuenta == "BBVA Platinum"
            and
            movimiento_corresponde_a_msi_bbva(
                movimiento,
                analisis_msi,
            )
        ):

            msi_excluidos.append(
                movimiento
            )

            continue

        descripcion = str(
            movimiento.get(
                "descripcion",
                "",
            )
        ).strip()

        try:

            monto = float(
                movimiento.get(
                    "monto",
                    0,
                )
            )

        except (
            ValueError,
            TypeError,
        ):

            continue

        try:

            fecha_operacion = (
                convertir_fecha_movimiento_banco(
                    movimiento.get(
                        "fecha_operacion",
                        "",
                    )
                )
            )

        except Exception:

            print()

            print(
                (
                    "⚠️ No pude convertir "
                    "la fecha de:"
                )
            )

            print(
                f"   {descripcion}"
            )

            continue

        categoria = (
            categorizar_cargo_regular(
                descripcion
            )
        )

        fila = [
            "Gasto",
            fecha_limite.strftime(
                "%d/%m/%Y"
            ),
            fecha_operacion.strftime(
                "%d/%m/%Y"
            ),
            monto,
            cuenta,
            "",
            descripcion,
            categoria[
                "categoria"
            ],
            "Contado",
            1,
            "Pendiente",
        ]

        propuestas.append(
            {
                "movimiento": movimiento,
                "fila": fila,
                "categoria": (
                    categoria[
                        "categoria"
                    ]
                ),
                "confianza": (
                    categoria[
                        "confianza"
                    ]
                ),
                "regla": (
                    categoria[
                        "regla"
                    ]
                ),
            }
        )

    return {
        "propuestas": propuestas,
        "msi_excluidos": msi_excluidos,
    }


# ============================================================
# MOSTRAR REGULARES FALTANTES
# ============================================================

def mostrar_cargos_regulares_faltantes(
    datos,
    conciliacion,
    analisis_msi,
):

    resultado = (
        preparar_cargos_regulares_faltantes(
            datos,
            conciliacion,
            analisis_msi,
        )
    )

    propuestas = resultado[
        "propuestas"
    ]

    msi_excluidos = resultado[
        "msi_excluidos"
    ]

    print()

    print(
        "=== CARGOS REGULARES FALTANTES ==="
    )

    print()

    print(
        (
            "Movimientos solo banco: "
            f"{len(conciliacion['solo_banco'])}"
        )
    )

    print(
        (
            "MSI excluidos: "
            f"{len(msi_excluidos)}"
        )
    )

    print(
        (
            "Cargos regulares propuestos: "
            f"{len(propuestas)}"
        )
    )

    if not propuestas:

        print()

        print(
            "✅ No hay cargos regulares faltantes."
        )

        return resultado

    print()

    print(
        "=== SIMULACIÓN DE ALTA REGULAR ==="
    )

    total = 0

    for numero, item in enumerate(
        propuestas,
        start=1,
    ):

        fila = item[
            "fila"
        ]

        total += float(
            fila[
                3
            ]
        )

        print()

        print(
            (
                f"{numero:02d}. "
                f"${fila[3]:,.2f}"
                f" | "
                f"{fila[6]}"
            )
        )

        print(
            (
                "    Categoría: "
                f"{item['categoria']}"
                f" | confianza "
                f"{item['confianza']}"
            )
        )

    print()

    print(
        (
            "Total propuesto: "
            f"${total:,.2f}"
        )
    )

    return resultado


# ============================================================
# REVISAR CARGO REGULAR
# ============================================================

def revisar_cargo_regular_existente(
    item,
    movimientos,
):

    fila = item[
        "fila"
    ]

    fecha_compra_propuesta = (
        convertir_fecha(
            fila[
                2
            ]
        )
    )

    monto_propuesto = float(
        fila[
            3
        ]
    )

    cuenta_propuesta = (
        normalizar_texto(
            fila[
                4
            ]
        )
    )

    descripcion_propuesta = (
        normalizar_texto(
            fila[
                6
            ]
        )
    )

    coincidencias = []

    for movimiento in movimientos:

        cuenta = normalizar_texto(
            movimiento.get(
                "Cuenta",
                "",
            )
        )

        if cuenta != cuenta_propuesta:

            continue

        tipo_pago = normalizar_texto(
            movimiento.get(
                "Tipo de Pago",
                "",
            )
        )

        if tipo_pago != "contado":

            continue

        try:

            plazos = int(
                float(
                    str(
                        movimiento.get(
                            "Numero de Plazos",
                            1,
                        )
                    )
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        if plazos != 1:

            continue

        try:

            monto = convertir_monto(
                movimiento.get(
                    "Monto de Compra",
                    0,
                )
            )

        except Exception:

            continue

        if abs(
            monto
            - monto_propuesto
        ) > 0.01:

            continue

        fecha_compra_valor = (
            movimiento.get(
                "Fecha de Compra",
                "",
            )
        )

        if not str(
            fecha_compra_valor
        ).strip():

            continue

        try:

            fecha_compra = (
                convertir_fecha(
                    fecha_compra_valor
                )
            )

        except Exception:

            continue

        if (
            fecha_compra.year
            != fecha_compra_propuesta.year
            or
            fecha_compra.month
            != fecha_compra_propuesta.month
            or
            fecha_compra.day
            != fecha_compra_propuesta.day
        ):

            continue

        coincidencias.append(
            movimiento
        )

    if len(coincidencias) == 0:

        return {
            "estado": "nuevo",
        }

    # Si solo hay una coincidencia,
    # comprobamos la descripción.

    if len(coincidencias) == 1:

        existente = coincidencias[
            0
        ]

        descripcion_existente = (
            normalizar_texto(
                existente.get(
                    "Descripcion",
                    "",
                )
            )
        )

        if (
            descripcion_existente
            == descripcion_propuesta
        ):

            return {
                "estado": "duplicado",
                "movimiento": existente,
            }

        return {
            "estado": "conflicto",
            "movimientos": [
                existente
            ],
        }

    # Más de una fila con mismo
    # banco + fecha + monto:
    # no adivinamos.

    return {
        "estado": "conflicto",
        "movimientos": coincidencias,
    }


# ============================================================
# PROTECCIÓN REGULARES
# ============================================================

def analizar_proteccion_regulares(
    analisis_regulares,
):

    propuestas = analisis_regulares.get(
        "propuestas",
        [],
    )

    movimientos = obtener_movimientos()

    duplicados = []
    conflictos = []
    nuevos_alta = []
    nuevos_media = []
    nuevos_baja = []

    for item in propuestas:

        revision = (
            revisar_cargo_regular_existente(
                item,
                movimientos,
            )
        )

        estado = revision[
            "estado"
        ]

        if estado == "duplicado":

            duplicados.append(
                {
                    "item": item,
                    "revision": revision,
                }
            )

            continue

        if estado == "conflicto":

            conflictos.append(
                {
                    "item": item,
                    "revision": revision,
                }
            )

            continue

        confianza = item[
            "confianza"
        ]

        if confianza == "Alta":

            nuevos_alta.append(
                item
            )

        elif confianza == "Media":

            nuevos_media.append(
                item
            )

        else:

            nuevos_baja.append(
                item
            )

    requieren_revision = (
        nuevos_media
        + nuevos_baja
        + [
            conflicto["item"]
            for conflicto
            in conflictos
        ]
    )

    return {
        "propuestas": propuestas,
        "duplicados": duplicados,
        "conflictos": conflictos,
        "nuevos_alta": nuevos_alta,
        "nuevos_media": nuevos_media,
        "nuevos_baja": nuevos_baja,
        "autoimportables": nuevos_alta,
        "requieren_revision": (
            requieren_revision
        ),
    }


# ============================================================
# MOSTRAR PROTECCIÓN REGULARES
# ============================================================

def mostrar_proteccion_regulares(
    analisis_regulares,
):

    proteccion = (
        analizar_proteccion_regulares(
            analisis_regulares
        )
    )

    print()

    print(
        "=== PROTECCIÓN DE CARGOS REGULARES ==="
    )

    print()

    print(
        (
            "Propuestos: "
            f"{len(proteccion['propuestas'])}"
        )
    )

    print(
        (
            "Duplicados: "
            f"{len(proteccion['duplicados'])}"
        )
    )

    print(
        (
            "Conflictos: "
            f"{len(proteccion['conflictos'])}"
        )
    )

    print()

    print(
        (
            "Nuevos confianza alta: "
            f"{len(proteccion['nuevos_alta'])}"
        )
    )

    print(
        (
            "Nuevos confianza media: "
            f"{len(proteccion['nuevos_media'])}"
        )
    )

    print(
        (
            "Nuevos confianza baja: "
            f"{len(proteccion['nuevos_baja'])}"
        )
    )

    print()

    print(
        (
            "Autoimportables: "
            f"{len(proteccion['autoimportables'])}"
        )
    )

    print(
        (
            "Requieren revisión: "
            f"{len(proteccion['requieren_revision'])}"
        )
    )

    if proteccion[
        "autoimportables"
    ]:

        print()

        print(
            "✅ AUTOIMPORTABLES"
        )

        print(
            "-" * 50
        )

        for item in proteccion[
            "autoimportables"
        ]:

            fila = item[
                "fila"
            ]

            print(
                (
                    f"${fila[3]:,.2f}"
                    f" | "
                    f"{fila[6]}"
                    f" | "
                    f"{item['categoria']}"
                )
            )

    if proteccion[
        "nuevos_media"
    ]:

        print()

        print(
            "🟡 CONFIANZA MEDIA"
        )

        print(
            "-" * 50
        )

        for item in proteccion[
            "nuevos_media"
        ]:

            fila = item[
                "fila"
            ]

            print(
                (
                    f"${fila[3]:,.2f}"
                    f" | "
                    f"{fila[6]}"
                    f" | "
                    f"{item['categoria']}"
                )
            )

    if proteccion[
        "nuevos_baja"
    ]:

        print()

        print(
            "⚠️ CONFIANZA BAJA"
        )

        print(
            "-" * 50
        )

        for item in proteccion[
            "nuevos_baja"
        ]:

            fila = item[
                "fila"
            ]

            print(
                (
                    f"${fila[3]:,.2f}"
                    f" | "
                    f"{fila[6]}"
                )
            )

    print()

    print(
        "ℹ️ La protección no escribió nada."
    )

    return proteccion


# ============================================================
# PASO 6C
# APLICAR REGULARES AUTOIMPORTABLES
# ============================================================

def aplicar_regulares_autoimportables(
    proteccion_regulares,
):

    candidatos = (
        proteccion_regulares.get(
            "autoimportables",
            [],
        )
    )

    if not candidatos:

        print()

        print(
            (
                "✅ No hay cargos regulares "
                "autoimportables."
            )
        )

        return {
            "agregadas": 0,
            "duplicadas": 0,
            "conflictos": 0,
        }

    # Segunda lectura de Sheets.
    #
    # No confiamos ciegamente en el análisis
    # que hicimos unos milisegundos antes.
    # La paranoia moderada es saludable aquí.

    movimientos_actuales = (
        obtener_movimientos()
    )

    nuevas = []
    duplicadas = []
    conflictos = []

    for item in candidatos:

        revision = (
            revisar_cargo_regular_existente(
                item,
                movimientos_actuales,
            )
        )

        estado = revision[
            "estado"
        ]

        if estado == "duplicado":

            duplicadas.append(
                item
            )

            continue

        if estado == "conflicto":

            conflictos.append(
                {
                    "item": item,
                    "revision": revision,
                }
            )

            continue

        nuevas.append(
            item
        )

    print()

    print(
        "=== PREVALIDACIÓN FINAL DE REGULARES ==="
    )

    print()

    print(
        (
            "Candidatos: "
            f"{len(candidatos)}"
        )
    )

    print(
        (
            "Ya existentes: "
            f"{len(duplicadas)}"
        )
    )

    print(
        (
            "Conflictos: "
            f"{len(conflictos)}"
        )
    )

    print(
        (
            "Nuevos seguros: "
            f"{len(nuevas)}"
        )
    )

    if conflictos:

        print()

        print(
            "⚠️ Hay conflictos."
        )

        print(
            (
                "Esos cargos NO serán "
                "registrados."
            )
        )

    if not nuevas:

        print()

        print(
            (
                "✅ No hay cargos regulares "
                "nuevos que escribir."
            )
        )

        return {
            "agregadas": 0,
            "duplicadas": len(
                duplicadas
            ),
            "conflictos": len(
                conflictos
            ),
        }

    filas = [
        item[
            "fila"
        ]
        for item
        in nuevas
    ]

    registrar_movimientos(
        filas
    )

    print()

    print(
        "✅ CARGOS REGULARES REGISTRADOS"
    )

    print(
        (
            "Filas agregadas: "
            f"{len(filas)}"
        )
    )

    print(
        (
            "Monto agregado: "
            f"${sum(float(fila[3]) for fila in filas):,.2f}"
        )
    )

    return {
        "agregadas": len(
            filas
        ),
        "duplicadas": len(
            duplicadas
        ),
        "conflictos": len(
            conflictos
        ),
    }


# ============================================================
# DETALLE DE DIFERENCIAS
# ============================================================

def mostrar_detalle_diferencias(
    conciliacion,
):

    print()

    print(
        "=== DETALLE DE DIFERENCIAS ==="
    )

    print()

    print(
        "⚠️ SOLO EN EL BANCO"
    )

    print(
        "-" * 50
    )

    if not conciliacion[
        "solo_banco"
    ]:

        print(
            "Ninguno."
        )

    else:

        for movimiento in conciliacion[
            "solo_banco"
        ]:

            print(
                (
                    f"${movimiento['monto']:,.2f} "
                    f"| {movimiento['descripcion']} "
                    f"| {movimiento['fecha_operacion']}"
                )
            )

    print()

    print(
        "🟡 SOLO EN SHEETS"
    )

    print(
        "-" * 50
    )

    if not conciliacion[
        "solo_interno"
    ]:

        print(
            "Ninguno."
        )

    else:

        for movimiento in conciliacion[
            "solo_interno"
        ]:

            original = movimiento.get(
                "movimiento",
                {},
            )

            print(
                (
                    f"${movimiento['monto']:,.2f} "
                    f"| {movimiento['descripcion']} "
                    f"| "
                    f"{original.get('Fecha de Pago', '')}"
                )
            )

    print()

    print(
        (
            "Monto coincidente: "
            f"${conciliacion['total_coincidente']:,.2f}"
        )
    )

    print(
        (
            "Solo banco: "
            f"${conciliacion['total_solo_banco']:,.2f}"
        )
    )

    print(
        (
            "Solo Sheets: "
            f"${conciliacion['total_solo_interno']:,.2f}"
        )
    )


# ============================================================
# IMPORTAR ESTADO
# ============================================================

def importar_estado(
    ruta_pdf,
    aplicar=False,
):

    print()

    if aplicar:

        print(
            "🔧 MODO APLICAR"
        )

        print(
            (
                "Los cambios validados podrán "
                "guardarse en Google Sheets."
            )
        )

    else:

        print(
            "🔍 MODO SIMULACIÓN"
        )

        print(
            "Google Sheets NO será modificado."
        )

    print()

    print(
        "📄 Leyendo estado..."
    )

    # ========================================================
    # EXTRAER PDF
    # ========================================================

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

    fecha_corte = datos.get(
        "fecha_corte"
    )

    fecha_limite = datos.get(
        "fecha_limite_pago"
    )

    pago_estado = datos.get(
        "pago_para_no_generar_intereses"
    )

    # ========================================================
    # DATOS OBLIGATORIOS
    # ========================================================

    faltantes = []

    if cuenta is None:
        faltantes.append(
            "cuenta"
        )

    if periodo is None:
        faltantes.append(
            "periodo"
        )

    if fecha_corte is None:
        faltantes.append(
            "fecha de corte"
        )

    if fecha_limite is None:
        faltantes.append(
            "fecha límite"
        )

    if pago_estado is None:
        faltantes.append(
            "pago para no generar intereses"
        )

    if faltantes:

        print()

        print(
            "❌ No se importó el estado."
        )

        print(
            (
                "Faltan datos: "
                + ", ".join(
                    faltantes
                )
            )
        )

        return

    # ========================================================
    # IDENTIFICACIÓN
    # ========================================================

    print()

    print(
        f"Cuenta: {cuenta}"
    )

    print(
        f"Periodo: {periodo}"
    )

    print(
        (
            "Pago requerido: "
            f"${pago_estado:,.2f}"
        )
    )

    # ========================================================
    # VALIDAR ESTADO
    # ========================================================

    validacion = validar_estado(
        datos,
        resumen,
        movimientos_banco,
    )

    print()

    print(
        "=== VALIDACIÓN DEL ESTADO ==="
    )

    if not validacion[
        "valido"
    ]:

        print()

        print(
            "❌ EL ESTADO NO CUADRA"
        )

        print(
            validacion.get(
                "error",
                (
                    "La ecuación del estado "
                    "no coincide."
                ),
            )
        )

        print()

        print(
            (
                "No se realizará ninguna "
                "escritura."
            )
        )

        return

    print()

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

    # ========================================================
    # CONCILIACIÓN INICIAL
    # ========================================================

    print()

    print(
        "=== CONCILIACIÓN CON MOVIMIENTOS ==="
    )

    print()

    conciliacion = (
        conciliar_con_sheets(
            datos,
            movimientos_banco,
        )
    )

    mostrar_resumen_conciliacion(
        conciliacion
    )

    # ========================================================
    # MSI
    # ========================================================

    analisis_msi = (
        mostrar_analisis_msi_bbva(
            datos,
            texto,
        )
    )

    resultado_msi = {
        "agregadas": 0,
        "duplicadas": 0,
        "conflictos": 0,
    }

    if (
        aplicar
        and
        analisis_msi.get(
            "aplica",
            False,
        )
    ):

        resultado_msi = (
            aplicar_msi_faltantes_bbva(
                analisis_msi
            )
        )

        if resultado_msi[
            "agregadas"
        ] > 0:

            print()

            print(
                "=== RECONCILIACIÓN DESPUÉS DE MSI ==="
            )

            print()

            conciliacion = (
                conciliar_con_sheets(
                    datos,
                    movimientos_banco,
                )
            )

            mostrar_resumen_conciliacion(
                conciliacion
            )

    # ========================================================
    # REGULARES
    # ========================================================

    analisis_regulares = (
        mostrar_cargos_regulares_faltantes(
            datos,
            conciliacion,
            analisis_msi,
        )
    )

    proteccion_regulares = (
        mostrar_proteccion_regulares(
            analisis_regulares
        )
    )

    resultado_regulares = {
        "agregadas": 0,
        "duplicadas": 0,
        "conflictos": 0,
    }

    # ========================================================
    # PASO 6C
    # AUTOIMPORTACIÓN DE CONFIANZA ALTA
    # ========================================================

    if aplicar:

        resultado_regulares = (
            aplicar_regulares_autoimportables(
                proteccion_regulares
            )
        )

        if resultado_regulares[
            "agregadas"
        ] > 0:

            print()

            print(
                "=== RECONCILIACIÓN FINAL ==="
            )

            print()

            conciliacion = (
                conciliar_con_sheets(
                    datos,
                    movimientos_banco,
                )
            )

            mostrar_resumen_conciliacion(
                conciliacion
            )

    # ========================================================
    # DIFERENCIAS FINALES
    # ========================================================

    mostrar_detalle_diferencias(
        conciliacion
    )

    # ========================================================
    # SEGURIDAD MSI
    # ========================================================

    invalidos_msi = []

    if analisis_msi.get(
        "aplica",
        False,
    ):

        invalidos_msi = (
            analisis_msi
            .get(
                "validacion",
                {},
            )
            .get(
                "invalidos",
                [],
            )
        )

    hay_problema_msi = (
        len(invalidos_msi) > 0
        or
        resultado_msi[
            "conflictos"
        ] > 0
    )

    # ========================================================
    # SEGURIDAD REGULARES
    # ========================================================

    hay_revision_regulares = (
        len(
            proteccion_regulares.get(
                "requieren_revision",
                [],
            )
        ) > 0
    )

    hay_conflicto_regulares = (
        resultado_regulares[
            "conflictos"
        ] > 0
        or
        len(
            proteccion_regulares.get(
                "conflictos",
                [],
            )
        ) > 0
    )

    # ========================================================
    # STATUS FINAL
    # ========================================================

    if (
        conciliacion[
            "conciliado"
        ]
        and not hay_problema_msi
        and not hay_revision_regulares
        and not hay_conflicto_regulares
    ):

        status = "Conciliado"

        print()

        print(
            "✅ ESTADO COMPLETAMENTE CONCILIADO"
        )

    else:

        status = "Revisar"

        print()

        print(
            "⚠️ ESTADO REQUIERE REVISIÓN"
        )

        if conciliacion[
            "solo_banco"
        ]:

            print(
                (
                    "Movimientos solo banco: "
                    f"{len(conciliacion['solo_banco'])}"
                )
            )

        if conciliacion[
            "solo_interno"
        ]:

            print(
                (
                    "Movimientos solo Sheets: "
                    f"{len(conciliacion['solo_interno'])}"
                )
            )

        if invalidos_msi:

            print(
                (
                    "MSI inconsistentes: "
                    f"{len(invalidos_msi)}"
                )
            )

        if hay_revision_regulares:

            print(
                (
                    "Regulares por revisar: "
                    f"{len(proteccion_regulares['requieren_revision'])}"
                )
            )

    # ========================================================
    # ESTADOS CUENTA
    # ========================================================

    estados_existentes = (
        obtener_estados_cuenta()
    )

    existente = buscar_estado_existente(
        estados_existentes,
        cuenta,
        periodo,
    )

    # ========================================================
    # YA EXISTE
    # ========================================================

    if existente is not None:

        print()

        print(
            "ℹ️ ESTADO YA REGISTRADO"
        )

        print(
            f"{cuenta} | {periodo}"
        )

        print(
            (
                "No se creará una fila "
                "duplicada."
            )
        )

        status_actual = str(
            existente.get(
                "Status",
                "",
            )
        ).strip()

        print()

        print(
            (
                "Status actual: "
                f"{status_actual}"
            )
        )

        print(
            (
                "Status calculado: "
                f"{status}"
            )
        )

        if not aplicar:

            print()

            print(
                "🔍 SIMULACIÓN"
            )

            if (
                status_actual
                != status
            ):

                print(
                    (
                        "Se actualizaría: "
                        f"{status_actual} → {status}"
                    )
                )

            else:

                print(
                    (
                        "El status ya coincide: "
                        f"{status}"
                    )
                )

            print(
                (
                    "Google Sheets "
                    "NO fue modificado."
                )
            )

            return

        actualizar_estado_existente(
            cuenta,
            periodo,
            status,
        )

        print()

        print(
            "=" * 45
        )

        print(
            "✅ ESTADO ACTUALIZADO"
        )

        print(
            "=" * 45
        )

        print()

        print(
            f"Cuenta: {cuenta}"
        )

        print(
            f"Periodo: {periodo}"
        )

        print(
            (
                "Pago requerido: "
                f"${pago_estado:,.2f}"
            )
        )

        print(
            f"Status: {status}"
        )

        return

    # ========================================================
    # ESTADO NUEVO
    # ========================================================

    fila_estado = [
        cuenta,
        periodo,
        fecha_corte,
        fecha_limite,
        pago_estado,
        status,
    ]

    if not aplicar:

        print()

        print(
            "=" * 45
        )

        print(
            "🔍 ESTADO NUEVO DETECTADO"
        )

        print(
            "=" * 45
        )

        print()

        print(
            f"Cuenta: {cuenta}"
        )

        print(
            f"Periodo: {periodo}"
        )

        print(
            (
                "Fecha corte: "
                f"{fecha_corte}"
            )
        )

        print(
            (
                "Fecha límite: "
                f"{fecha_limite}"
            )
        )

        print(
            (
                "Pago requerido: "
                f"${pago_estado:,.2f}"
            )
        )

        print(
            (
                "Status propuesto: "
                f"{status}"
            )
        )

        print()

        print(
            (
                "Google Sheets "
                "NO fue modificado."
            )
        )

        return

    registrar_estado_cuenta(
        fila_estado
    )

    print()

    print(
        "=" * 45
    )

    print(
        "✅ ESTADO IMPORTADO"
    )

    print(
        "=" * 45
    )

    print()

    print(
        f"Cuenta: {cuenta}"
    )

    print(
        f"Periodo: {periodo}"
    )

    print(
        (
            "Pago requerido: "
            f"${pago_estado:,.2f}"
        )
    )

    print(
        f"Status: {status}"
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

    if len(rutas) != 1:

        print(
            "Uso:"
        )

        print()

        print(
            (
                "python importar_estado.py "
                "\"estados/archivo.pdf\""
            )
        )

        print()

        print(
            (
                "python importar_estado.py "
                "\"estados/archivo.pdf\" "
                "--aplicar"
            )
        )

        return

    importar_estado(
        rutas[0],
        aplicar=aplicar,
    )


if __name__ == "__main__":

    main()