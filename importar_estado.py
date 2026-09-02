import re
import sys
from datetime import datetime
from difflib import SequenceMatcher

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


# Todo movimiento bancario nuevo entra sin categoría.
# La subcategoría se asigna después desde Telegram.
SUBCATEGORIA_PENDIENTE = "Sin clasificar"


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
# ACTUALIZAR ESTADO EXISTENTE
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
                + ", ".join(faltantes)
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
                + ", ".join(faltantes)
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
# FECHAS BANCARIAS
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
                "Fecha bancaria "
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
                "Mes no reconocido: "
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
# DETECCIÓN GENÉRICA DE CUOTAS
# ============================================================

def detectar_cuota_en_descripcion(
    descripcion,
):

    texto = str(
        descripcion
    ).strip().lower()

    coincidencia = re.search(
        (
            r"(?<!\d)"
            r"0*(\d{1,2})"
            r"\s+de\s+"
            r"0*(\d{1,2})"
            r"(?!\d)"
        ),
        texto,
        flags=re.IGNORECASE,
    )

    if not coincidencia:
        return {
            "es_cuota": False,
            "numero": None,
            "plazos": None,
            "texto_detectado": None,
        }

    try:
        numero = int(
            coincidencia.group(1)
        )

        plazos = int(
            coincidencia.group(2)
        )

    except (
        ValueError,
        TypeError,
    ):
        return {
            "es_cuota": False,
            "numero": None,
            "plazos": None,
            "texto_detectado": None,
        }

    if not (
        2 <= plazos <= 60
        and 1 <= numero <= plazos
    ):
        return {
            "es_cuota": False,
            "numero": None,
            "plazos": None,
            "texto_detectado": None,
        }

    return {
        "es_cuota": True,
        "numero": numero,
        "plazos": plazos,
        "texto_detectado": (
            coincidencia.group(0)
        ),
    }


# ============================================================
# DETECTAR PLANES MSI BBVA
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
                != plan[
                    "plazos"
                ]
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
                - plan[
                    "cuota"
                ]
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
# VALIDAR RECONSTRUCCIÓN MSI BBVA
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
            plan[
                "monto_original"
            ],
            plan[
                "plazos"
            ],
            fecha_compra,
            plan[
                "descripcion"
            ],
            cuenta,
        )

        cuota_actual = None

        for cuota in cuotas:

            if (
                cuota[
                    "numero"
                ]
                == plan[
                    "numero"
                ]
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
                cuota[
                    "monto"
                ]
                for cuota
                in cuotas
            ),
            2,
        )

        diferencia_total = round(
            total_reconstruido
            - plan[
                "monto_original"
            ],
            2,
        )

        diferencia_cuota = round(
            cuota_actual[
                "monto"
            ]
            - plan[
                "cuota"
            ],
            2,
        )

        valido = (
            abs(
                diferencia_total
            ) <= 0.01
            and
            abs(
                diferencia_cuota
            ) <= 0.01
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
# PREPARAR FILAS MSI BBVA
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
                SUBCATEGORIA_PENDIENTE,
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
# REVISAR CUOTA MSI BBVA
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

    if len(
        coincidencias
    ) == 0:

        return {
            "estado": "nuevo",
        }

    if len(
        coincidencias
    ) == 1:

        return {
            "estado": "duplicado",
            "movimiento": (
                coincidencias[
                    0
                ]
            ),
        }

    return {
        "estado": "conflicto",
        "movimientos": coincidencias,
    }


# ============================================================
# APLICAR MSI BBVA
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
                item[
                    "fila"
                ],
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
        (
            "Filas propuestas: "
            f"{len(filas_propuestas)}"
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
            "Nuevas: "
            f"{len(nuevas)}"
        )
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
        (
            "Filas agregadas: "
            f"{len(filas_sheets)}"
        )
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
# MOSTRAR MSI BBVA
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

    if analisis_msi[
        "faltantes"
    ]:

        print()

        print(
            "⚠️ PLANES MSI FALTANTES"
        )

        print(
            "-" * 50
        )

        for plan in analisis_msi[
            "faltantes"
        ]:

            print(
                (
                    f"{plan['numero']:02d}/"
                    f"{plan['plazos']:02d}"
                    f" | "
                    f"${plan['cuota']:,.2f}"
                    f" | original "
                    f"${plan['monto_original']:,.2f}"
                )
            )

            print(
                f"   {plan['descripcion']}"
            )

    else:

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
            f"   {plan['descripcion']}"
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

        else:

            error = resultado.get(
                "error"
            )

            if error:

                print(
                    f"   ⚠️ {error}"
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
# DETECTAR SI MOVIMIENTO BBVA ES MSI
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
            - plan[
                "cuota"
            ]
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
            .split(
                ";"
            )[0]
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
# CATEGORIZACIÓN
# ============================================================

# El importador no decide categorías por comercio.
# Todo cargo nuevo entra como "Sin clasificar" y se
# categoriza después desde Telegram mediante botones.


# ============================================================
# PREPARAR CARGOS REGULARES FALTANTES
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
    cuotas_excluidas = []

    for movimiento in conciliacion[
        "solo_banco"
    ]:

        descripcion = str(
            movimiento.get(
                "descripcion",
                "",
            )
        ).strip()

        cuota_generica = (
            detectar_cuota_en_descripcion(
                descripcion
            )
        )

        if cuota_generica[
            "es_cuota"
        ]:
            cuotas_excluidas.append(
                {
                    "movimiento": movimiento,
                    "motivo": "patron_cuota",
                    "numero": cuota_generica[
                        "numero"
                    ],
                    "plazos": cuota_generica[
                        "plazos"
                    ],
                }
            )
            continue

        if (
            cuenta == "BBVA Platinum"
            and movimiento_corresponde_a_msi_bbva(
                movimiento,
                analisis_msi,
            )
        ):
            cuotas_excluidas.append(
                {
                    "movimiento": movimiento,
                    "motivo": "msi_bbva",
                    "numero": None,
                    "plazos": None,
                }
            )
            continue

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
                "⚠️ No pude convertir la fecha de:"
            )
            print(
                f"   {descripcion}"
            )
            continue

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
            SUBCATEGORIA_PENDIENTE,
            "Contado",
            1,
            "Pendiente",
        ]

        propuestas.append(
            {
                "movimiento": movimiento,
                "fila": fila,
            }
        )

    return {
        "propuestas": propuestas,
        "cuotas_excluidas": cuotas_excluidas,
    }


# ============================================================
# MOSTRAR CARGOS REGULARES
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

    cuotas_excluidas = resultado[
        "cuotas_excluidas"
    ]

    print()
    print(
        "=== CARGOS REGULARES FALTANTES ==="
    )
    print()

    print(
        "Movimientos solo banco: "
        f"{len(conciliacion['solo_banco'])}"
    )

    print(
        "Cuotas/MSI excluidos: "
        f"{len(cuotas_excluidas)}"
    )

    print(
        "Cargos regulares propuestos: "
        f"{len(propuestas)}"
    )

    if cuotas_excluidas:
        print()
        print(
            "=== CUOTAS DETECTADAS ==="
        )

        for item in cuotas_excluidas:
            movimiento = item[
                "movimiento"
            ]

            if (
                item["numero"] is not None
                and item["plazos"] is not None
            ):
                cuota_texto = (
                    f"{item['numero']:02d}/"
                    f"{item['plazos']:02d}"
                )
            else:
                cuota_texto = "MSI BBVA"

            print(
                f"💳 {cuota_texto} | "
                f"${movimiento['monto']:,.2f} | "
                f"{movimiento['descripcion']}"
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
            fila[3]
        )

        print()
        print(
            f"{numero:02d}. "
            f"${fila[3]:,.2f} | "
            f"{fila[6]}"
        )

        print(
            "    Fecha compra: "
            f"{fila[2]}"
        )

        print(
            "    Fecha pago: "
            f"{fila[1]}"
        )

        print(
            "    Subcategoría: "
            f"{SUBCATEGORIA_PENDIENTE}"
        )

    print()
    print(
        "Total propuesto: "
        f"${total:,.2f}"
    )

    return resultado


# ============================================================
# NORMALIZAR DESCRIPCIÓN DE CUOTA
# ============================================================

def normalizar_descripcion_cuota(
    descripcion,
):

    texto = normalizar_texto(
        descripcion
    )

    texto = re.sub(
        (
            r"(?<!\d)"
            r"0*\d{1,3}"
            r"\s+de\s+"
            r"0*\d{1,3}"
            r"(?!\d)"
        ),
        " ",
        texto,
        flags=re.IGNORECASE,
    )

    texto = re.sub(
        (
            r"(?<!\d)"
            r"0*\d{1,3}"
            r"\s*/\s*"
            r"0*\d{1,3}"
            r"(?!\d)"
        ),
        " ",
        texto,
        flags=re.IGNORECASE,
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()

    return texto


# ============================================================
# SIMILITUD CUOTA
# ============================================================

def calcular_similitud_cuota(
    descripcion_banco,
    descripcion_sheets,
):

    banco = normalizar_descripcion_cuota(
        descripcion_banco
    )

    sheets = normalizar_descripcion_cuota(
        descripcion_sheets
    )

    if not banco or not sheets:
        return 0.0

    if banco == sheets:
        return 1.0

    if (
        banco in sheets
        or sheets in banco
    ):
        return 0.95

    return SequenceMatcher(
        None,
        banco,
        sheets,
    ).ratio()


# ============================================================
# OBTENER ORIGINAL INTERNO
# ============================================================

def obtener_original_interno(
    movimiento_interno,
):

    return movimiento_interno.get(
        "movimiento",
        movimiento_interno,
    )


# ============================================================
# CANDIDATO DE CUOTA
# ============================================================

def candidato_coincide_con_cuota(
    datos,
    cuota_detectada,
    movimiento_interno,
):

    if (
        cuota_detectada.get(
            "motivo"
        )
        != "patron_cuota"
    ):
        return None

    if (
        cuota_detectada.get(
            "plazos"
        )
        is None
    ):
        return None

    banco = cuota_detectada[
        "movimiento"
    ]

    original = obtener_original_interno(
        movimiento_interno
    )

    cuenta_objetivo = normalizar_texto(
        datos[
            "cuenta"
        ]
    )

    cuenta_sheets = normalizar_texto(
        original.get(
            "Cuenta",
            "",
        )
    )

    if cuenta_sheets != cuenta_objetivo:
        return None

    tipo_pago = normalizar_texto(
        original.get(
            "Tipo de Pago",
            "",
        )
    )

    if tipo_pago != "meses":
        return None

    try:

        plazos_sheets = int(
            float(
                str(
                    original.get(
                        "Numero de Plazos",
                        0,
                    )
                )
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if (
        plazos_sheets
        != cuota_detectada[
            "plazos"
        ]
    ):
        return None

    try:

        monto_sheets = convertir_monto(
            original.get(
                "Monto de Compra",
                0,
            )
        )

        monto_banco = float(
            banco.get(
                "monto",
                0,
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if abs(
        monto_sheets
        - monto_banco
    ) > 0.01:
        return None

    try:

        fecha_sheets = convertir_fecha(
            original.get(
                "Fecha de Pago",
                "",
            )
        )

        fecha_limite = convertir_fecha(
            datos[
                "fecha_limite_pago"
            ]
        )

    except Exception:
        return None

    if (
        fecha_sheets.year
        != fecha_limite.year
        or
        fecha_sheets.month
        != fecha_limite.month
        or
        fecha_sheets.day
        != fecha_limite.day
    ):
        return None

    similitud = calcular_similitud_cuota(
        banco.get(
            "descripcion",
            "",
        ),
        original.get(
            "Descripcion",
            "",
        ),
    )

    return {
        "interno": movimiento_interno,
        "original": original,
        "similitud": similitud,
    }


# ============================================================
# CONCILIAR CUOTAS MULTIBANCO
# ============================================================

def conciliar_cuotas_genericas(
    datos,
    conciliacion,
    analisis_regulares,
    mostrar=True,
):

    cuotas_todas = analisis_regulares.get(
        "cuotas_excluidas",
        [],
    )

    cuotas = [
        cuota
        for cuota
        in cuotas_todas
        if (
            cuota.get(
                "motivo"
            )
            == "patron_cuota"
            and
            cuota.get(
                "numero"
            )
            is not None
            and
            cuota.get(
                "plazos"
            )
            is not None
        )
    ]

    solo_banco = list(
        conciliacion[
            "solo_banco"
        ]
    )

    solo_interno = list(
        conciliacion[
            "solo_interno"
        ]
    )

    existentes = []
    faltantes = []
    ambiguas = []

    indices_internos_usados = set()
    indices_banco_resueltos = set()

    for cuota in cuotas:

        candidatos = []

        for indice, movimiento_interno in enumerate(
            solo_interno
        ):

            if (
                indice
                in indices_internos_usados
            ):
                continue

            candidato = (
                candidato_coincide_con_cuota(
                    datos,
                    cuota,
                    movimiento_interno,
                )
            )

            if candidato is None:
                continue

            candidato[
                "indice_interno"
            ] = indice

            candidatos.append(
                candidato
            )

        if not candidatos:

            faltantes.append(
                cuota
            )

            continue

        if len(
            candidatos
        ) == 1:

            ganador = candidatos[
                0
            ]

            if ganador[
                "similitud"
            ] < 0.20:

                ambiguas.append(
                    {
                        "cuota": cuota,
                        "candidatos": (
                            candidatos
                        ),
                    }
                )

                continue

            existentes.append(
                {
                    "cuota": cuota,
                    "candidato": ganador,
                }
            )

            indices_internos_usados.add(
                ganador[
                    "indice_interno"
                ]
            )

            continue

        candidatos.sort(
            key=lambda item: (
                item[
                    "similitud"
                ]
            ),
            reverse=True,
        )

        mejor = candidatos[
            0
        ]

        segundo = candidatos[
            1
        ]

        diferencia = (
            mejor[
                "similitud"
            ]
            - segundo[
                "similitud"
            ]
        )

        if (
            mejor[
                "similitud"
            ] >= 0.55
            and
            diferencia >= 0.15
        ):

            existentes.append(
                {
                    "cuota": cuota,
                    "candidato": mejor,
                }
            )

            indices_internos_usados.add(
                mejor[
                    "indice_interno"
                ]
            )

        else:

            ambiguas.append(
                {
                    "cuota": cuota,
                    "candidatos": (
                        candidatos
                    ),
                }
            )

    for resuelta in existentes:

        movimiento_objetivo = (
            resuelta[
                "cuota"
            ][
                "movimiento"
            ]
        )

        for indice, movimiento in enumerate(
            solo_banco
        ):

            if (
                indice
                in indices_banco_resueltos
            ):
                continue

            if (
                movimiento
                is movimiento_objetivo
                or
                movimiento
                == movimiento_objetivo
            ):

                indices_banco_resueltos.add(
                    indice
                )

                resuelta[
                    "indice_banco"
                ] = indice

                break

    nuevas_coincidencias = list(
        conciliacion[
            "coincidencias"
        ]
    )

    for resuelta in existentes:

        indice_banco = resuelta.get(
            "indice_banco"
        )

        if indice_banco is None:
            continue

        indice_interno = (
            resuelta[
                "candidato"
            ][
                "indice_interno"
            ]
        )

        nuevas_coincidencias.append(
            {
                "banco": (
                    solo_banco[
                        indice_banco
                    ]
                ),
                "interno": (
                    solo_interno[
                        indice_interno
                    ]
                ),
            }
        )

    nuevos_solo_banco = [
        movimiento
        for indice, movimiento
        in enumerate(
            solo_banco
        )
        if (
            indice
            not in indices_banco_resueltos
        )
    ]

    nuevos_solo_interno = [
        movimiento
        for indice, movimiento
        in enumerate(
            solo_interno
        )
        if (
            indice
            not in indices_internos_usados
        )
    ]

    total_coincidente = round(
        sum(
            float(
                item[
                    "banco"
                ][
                    "monto"
                ]
            )
            for item
            in nuevas_coincidencias
        ),
        2,
    )

    total_solo_banco = round(
        sum(
            float(
                movimiento[
                    "monto"
                ]
            )
            for movimiento
            in nuevos_solo_banco
        ),
        2,
    )

    total_solo_interno = round(
        sum(
            float(
                movimiento[
                    "monto"
                ]
            )
            for movimiento
            in nuevos_solo_interno
        ),
        2,
    )

    conciliacion_actualizada = {
        "conciliado": (
            len(
                nuevos_solo_banco
            ) == 0
            and
            len(
                nuevos_solo_interno
            ) == 0
        ),
        "coincidencias": (
            nuevas_coincidencias
        ),
        "solo_banco": (
            nuevos_solo_banco
        ),
        "solo_interno": (
            nuevos_solo_interno
        ),
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

    analisis = {
        "detectadas": cuotas,
        "existentes": existentes,
        "faltantes": faltantes,
        "ambiguas": ambiguas,
    }

    if mostrar:

        print()

        print(
            "=== CONCILIACIÓN DE CUOTAS MULTIBANCO ==="
        )

        print()

        print(
            (
                "Cuotas detectadas: "
                f"{len(cuotas)}"
            )
        )

        print(
            (
                "Cuotas ya existentes: "
                f"{len(existentes)}"
            )
        )

        print(
            (
                "Cuotas faltantes: "
                f"{len(faltantes)}"
            )
        )

        print(
            (
                "Cuotas ambiguas: "
                f"{len(ambiguas)}"
            )
        )

        if existentes:

            print()

            print(
                "✅ CUOTAS YA REGISTRADAS"
            )

            print(
                "-" * 50
            )

            for item in existentes:

                cuota = item[
                    "cuota"
                ]

                banco = cuota[
                    "movimiento"
                ]

                candidato = item[
                    "candidato"
                ]

                print(
                    (
                        f"{cuota['numero']:02d}/"
                        f"{cuota['plazos']:02d}"
                        f" | "
                        f"${banco['monto']:,.2f}"
                        f" | "
                        f"{banco['descripcion']}"
                    )
                )

                print(
                    (
                        "   Similitud descripción: "
                        f"{candidato['similitud']:.0%}"
                    )
                )

        if faltantes:

            print()

            print(
                "⚠️ CUOTAS FALTANTES EN SHEETS"
            )

            print(
                "-" * 50
            )

            for cuota in faltantes:

                banco = cuota[
                    "movimiento"
                ]

                print(
                    (
                        f"{cuota['numero']:02d}/"
                        f"{cuota['plazos']:02d}"
                        f" | "
                        f"${banco['monto']:,.2f}"
                        f" | "
                        f"{banco['descripcion']}"
                    )
                )

                print(
                    (
                        "   No se reconstruirá "
                        "automáticamente."
                    )
                )

        if ambiguas:

            print()

            print(
                "🟡 CUOTAS AMBIGUAS"
            )

            print(
                "-" * 50
            )

            for item in ambiguas:

                cuota = item[
                    "cuota"
                ]

                banco = cuota[
                    "movimiento"
                ]

                print()

                print(
                    (
                        f"{cuota['numero']:02d}/"
                        f"{cuota['plazos']:02d}"
                        f" | "
                        f"${banco['monto']:,.2f}"
                        f" | "
                        f"{banco['descripcion']}"
                    )
                )

                for candidato in item[
                    "candidatos"
                ]:

                    original = candidato[
                        "original"
                    ]

                    print(
                        (
                            "   Sheets: "
                            f"{original.get('Descripcion', '')}"
                            f" | similitud "
                            f"{candidato['similitud']:.0%}"
                        )
                    )

    return (
        analisis,
        conciliacion_actualizada,
    )


# ============================================================
# PREPARAR FILAS DE CUOTAS GENÉRICAS
# ============================================================

def preparar_filas_cuotas_genericas(
    datos,
    analisis_cuotas,
):

    fecha_limite = convertir_fecha(
        datos[
            "fecha_limite_pago"
        ]
    )

    cuenta = datos[
        "cuenta"
    ]

    propuestas = []

    for cuota in analisis_cuotas.get(
        "faltantes",
        [],
    ):

        if (
            cuota.get(
                "motivo"
            )
            != "patron_cuota"
        ):
            continue

        if (
            cuota.get(
                "numero"
            )
            is None
            or
            cuota.get(
                "plazos"
            )
            is None
        ):
            continue

        movimiento = cuota[
            "movimiento"
        ]

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

        descripcion = str(
            movimiento.get(
                "descripcion",
                "",
            )
        ).strip()

        fila = [
            "Gasto",
            fecha_limite.strftime(
                "%d/%m/%Y"
            ),
            "",
            monto,
            cuenta,
            "",
            descripcion,
            SUBCATEGORIA_PENDIENTE,
            "Meses",
            cuota[
                "plazos"
            ],
            "Pendiente",
        ]

        propuestas.append(
            {
                "fila": fila,
                "cuota": cuota,
            }
        )

    return propuestas


# ============================================================
# REVISAR CUOTA GENÉRICA EXISTENTE
# ============================================================

def revisar_cuota_generica_existente(
    propuesta,
    movimientos,
):

    fila = propuesta[
        "fila"
    ]

    fecha_pago_propuesta = (
        convertir_fecha(
            fila[
                1
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
        fila[
            6
        ]
    )

    plazos_propuestos = int(
        fila[
            9
        ]
    )

    candidatos = []

    for movimiento in movimientos:

        cuenta = normalizar_texto(
            movimiento.get(
                "Cuenta",
                "",
            )
        )

        if (
            cuenta
            != cuenta_propuesta
        ):
            continue

        tipo_pago = normalizar_texto(
            movimiento.get(
                "Tipo de Pago",
                "",
            )
        )

        if tipo_pago != "meses":
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
            TypeError,
            ValueError,
        ):
            continue

        if (
            plazos
            != plazos_propuestos
        ):
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

            fecha_pago = convertir_fecha(
                movimiento.get(
                    "Fecha de Pago",
                    "",
                )
            )

        except Exception:
            continue

        if (
            fecha_pago.year
            != fecha_pago_propuesta.year
            or
            fecha_pago.month
            != fecha_pago_propuesta.month
            or
            fecha_pago.day
            != fecha_pago_propuesta.day
        ):
            continue

        similitud = (
            calcular_similitud_cuota(
                descripcion_propuesta,
                movimiento.get(
                    "Descripcion",
                    "",
                ),
            )
        )

        candidatos.append(
            {
                "movimiento": movimiento,
                "similitud": similitud,
            }
        )

    if not candidatos:

        return {
            "estado": "nuevo",
        }

    if len(
        candidatos
    ) == 1:

        candidato = candidatos[
            0
        ]

        if (
            candidato[
                "similitud"
            ] >= 0.20
        ):

            return {
                "estado": "duplicado",
                "candidato": candidato,
            }

        return {
            "estado": "conflicto",
            "candidatos": candidatos,
        }

    candidatos.sort(
        key=lambda item: (
            item[
                "similitud"
            ]
        ),
        reverse=True,
    )

    mejor = candidatos[
        0
    ]

    segundo = candidatos[
        1
    ]

    diferencia = (
        mejor[
            "similitud"
        ]
        - segundo[
            "similitud"
        ]
    )

    if (
        mejor[
            "similitud"
        ] >= 0.55
        and
        diferencia >= 0.15
    ):

        return {
            "estado": "duplicado",
            "candidato": mejor,
        }

    return {
        "estado": "conflicto",
        "candidatos": candidatos,
    }


# ============================================================
# ANALIZAR / SIMULAR ALTA DE CUOTAS
# ============================================================

def analizar_alta_cuotas_genericas(
    datos,
    analisis_cuotas,
    mostrar=True,
):

    propuestas = (
        preparar_filas_cuotas_genericas(
            datos,
            analisis_cuotas,
        )
    )

    movimientos = (
        obtener_movimientos()
    )

    nuevas = []
    duplicadas = []
    conflictos = []

    for propuesta in propuestas:

        revision = (
            revisar_cuota_generica_existente(
                propuesta,
                movimientos,
            )
        )

        estado = revision[
            "estado"
        ]

        if estado == "nuevo":

            nuevas.append(
                propuesta
            )

        elif estado == "duplicado":

            duplicadas.append(
                {
                    "propuesta": propuesta,
                    "revision": revision,
                }
            )

        else:

            conflictos.append(
                {
                    "propuesta": propuesta,
                    "revision": revision,
                }
            )

    resultado = {
        "propuestas": propuestas,
        "nuevas": nuevas,
        "duplicadas": duplicadas,
        "conflictos": conflictos,
    }

    if not mostrar:
        return resultado

    print()

    print(
        "=== SIMULACIÓN DE ALTA DE CUOTAS ==="
    )

    print()

    print(
        (
            "Cuotas faltantes: "
            f"{len(analisis_cuotas.get('faltantes', []))}"
        )
    )

    print(
        (
            "Cuotas propuestas: "
            f"{len(propuestas)}"
        )
    )

    print(
        (
            "Nuevas: "
            f"{len(nuevas)}"
        )
    )

    print(
        (
            "Duplicadas: "
            f"{len(duplicadas)}"
        )
    )

    print(
        (
            "Conflictos: "
            f"{len(conflictos)}"
        )
    )

    if nuevas:

        print()

        print(
            "🆕 CUOTAS PROPUESTAS"
        )

        print(
            "-" * 50
        )

        for numero, propuesta in enumerate(
            nuevas,
            start=1,
        ):

            fila = propuesta[
                "fila"
            ]

            cuota = propuesta[
                "cuota"
            ]

            print()

            print(
                (
                    f"{numero:02d}. "
                    f"{cuota['numero']:02d}/"
                    f"{cuota['plazos']:02d}"
                    f" | "
                    f"${fila[3]:,.2f}"
                    f" | "
                    f"{fila[6]}"
                )
            )

            print(
                (
                    "    Fecha pago: "
                    f"{fila[1]}"
                )
            )

            print(
                "    Fecha compra: no disponible"
            )

            print(
                (
                    "    Cuenta: "
                    f"{fila[4]}"
                )
            )

            print(
                "    Tipo pago: Meses"
            )

            print(
                (
                    "    Número de plazos: "
                    f"{fila[9]}"
                )
            )

            print(
                (
                    "    Status: "
                    f"{fila[10]}"
                )
            )

    if duplicadas:

        print()

        print(
            "✅ CUOTAS YA EXISTENTES"
        )

        print(
            "-" * 50
        )

        for item in duplicadas:

            propuesta = item[
                "propuesta"
            ]

            revision = item[
                "revision"
            ]

            fila = propuesta[
                "fila"
            ]

            similitud = (
                revision[
                    "candidato"
                ][
                    "similitud"
                ]
            )

            print(
                (
                    f"${fila[3]:,.2f}"
                    f" | "
                    f"{fila[6]}"
                    f" | similitud "
                    f"{similitud:.0%}"
                )
            )

    if conflictos:

        print()

        print(
            "⚠️ CUOTAS CON CONFLICTO"
        )

        print(
            "-" * 50
        )

        for conflicto in conflictos:

            propuesta = conflicto[
                "propuesta"
            ]

            fila = propuesta[
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
        (
            "ℹ️ Esta fase es una simulación. "
            "Todavía no se escribió ninguna cuota."
        )
    )

    return resultado


# ============================================================
# 6C.4
# APLICAR CUOTAS GENÉRICAS
# ============================================================

def aplicar_cuotas_genericas(
    analisis_alta_cuotas,
):

    candidatos = (
        analisis_alta_cuotas.get(
            "nuevas",
            [],
        )
    )

    if not candidatos:

        print()

        print(
            "✅ No hay cuotas genéricas nuevas por registrar."
        )

        return {
            "agregadas": 0,
            "duplicadas": 0,
            "conflictos": 0,
        }

    # Segunda lectura justo antes de escribir.
    # Esta es la protección contra cambios ocurridos
    # entre la simulación y el momento de aplicar.

    movimientos_actuales = (
        obtener_movimientos()
    )

    nuevas = []
    duplicadas = []
    conflictos = []

    for propuesta in candidatos:

        revision = (
            revisar_cuota_generica_existente(
                propuesta,
                movimientos_actuales,
            )
        )

        estado = revision[
            "estado"
        ]

        if estado == "nuevo":

            nuevas.append(
                propuesta
            )

        elif estado == "duplicado":

            duplicadas.append(
                {
                    "propuesta": propuesta,
                    "revision": revision,
                }
            )

        else:

            conflictos.append(
                {
                    "propuesta": propuesta,
                    "revision": revision,
                }
            )

    print()

    print(
        "=== PREVALIDACIÓN FINAL DE CUOTAS ==="
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
            "Nuevas seguras: "
            f"{len(nuevas)}"
        )
    )

    # Política all-or-nothing:
    # si aparece un conflicto, no escribimos ninguna
    # cuota nueva en este bloque.

    if conflictos:

        print()

        print(
            "🛑 ALTA DE CUOTAS CANCELADA"
        )

        print(
            (
                "Existe al menos un conflicto. "
                "No se escribió ninguna cuota."
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

    if not nuevas:

        print()

        print(
            "✅ No hay cuotas nuevas que escribir."
        )

        return {
            "agregadas": 0,
            "duplicadas": len(
                duplicadas
            ),
            "conflictos": 0,
        }

    filas = [
        propuesta[
            "fila"
        ]
        for propuesta
        in nuevas
    ]

    registrar_movimientos(
        filas
    )

    print()

    print(
        "✅ CUOTAS GENÉRICAS REGISTRADAS"
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
        "conflictos": 0,
    }


# ============================================================
# REVISAR CARGO REGULAR EXISTENTE
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

    if len(
        coincidencias
    ) == 0:

        return {
            "estado": "nuevo",
        }

    if len(
        coincidencias
    ) == 1:

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

    return {
        "estado": "conflicto",
        "movimientos": coincidencias,
    }


# ============================================================
# PROTECCIÓN DE REGULARES
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
    nuevos = []

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

        nuevos.append(
            item
        )

    requieren_revision = [
        conflicto[
            "item"
        ]
        for conflicto
        in conflictos
    ]

    return {
        "propuestas": propuestas,
        "duplicados": duplicados,
        "conflictos": conflictos,
        "autoimportables": nuevos,
        "requieren_revision": (
            requieren_revision
        ),
    }


# ============================================================
# MOSTRAR PROTECCIÓN DE REGULARES
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
        "Propuestos: "
        f"{len(proteccion['propuestas'])}"
    )

    print(
        "Duplicados: "
        f"{len(proteccion['duplicados'])}"
    )

    print(
        "Conflictos: "
        f"{len(proteccion['conflictos'])}"
    )

    print(
        "Listos para importar: "
        f"{len(proteccion['autoimportables'])}"
    )

    if proteccion[
        "autoimportables"
    ]:
        print()
        print(
            "✅ MOVIMIENTOS NUEVOS"
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
                f"${fila[3]:,.2f} | "
                f"{fila[6]} | "
                f"{SUBCATEGORIA_PENDIENTE}"
            )

    if proteccion[
        "conflictos"
    ]:
        print()
        print(
            "❌ CONFLICTOS"
        )
        print(
            "-" * 50
        )

        for conflicto in proteccion[
            "conflictos"
        ]:
            fila = conflicto[
                "item"
            ][
                "fila"
            ]

            print(
                f"${fila[3]:,.2f} | "
                f"{fila[6]}"
            )

    print()
    print(
        "ℹ️ La protección no escribió nada."
    )

    return proteccion


# ============================================================
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
            "✅ No hay cargos regulares nuevos por registrar."
        )

        return {
            "agregadas": 0,
            "duplicadas": 0,
            "conflictos": 0,
        }

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
        "Candidatos: "
        f"{len(candidatos)}"
    )

    print(
        "Ya existentes: "
        f"{len(duplicadas)}"
    )

    print(
        "Conflictos: "
        f"{len(conflictos)}"
    )

    print(
        "Nuevos seguros: "
        f"{len(nuevas)}"
    )

    if conflictos:
        print()
        print(
            "⚠️ Los conflictos NO serán registrados."
        )

    if not nuevas:
        print()
        print(
            "✅ No hay cargos regulares nuevos que escribir."
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
        "Filas agregadas: "
        f"{len(filas)}"
    )

    print(
        "Monto agregado: "
        f"${sum(float(fila[3]) for fila in filas):,.2f}"
    )

    print(
        "Subcategoría inicial: "
        f"{SUBCATEGORIA_PENDIENTE}"
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
# RECALCULAR ANÁLISIS DESDE CONCILIACIÓN ACTUAL
# ============================================================

def recalcular_analisis_actual(
    datos,
    conciliacion,
    analisis_msi,
):

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

    proteccion_regulares = (
        analizar_proteccion_regulares(
            analisis_regulares
        )
    )

    return (
        conciliacion,
        analisis_regulares,
        analisis_cuotas,
        proteccion_regulares,
    )


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
    # VALIDACIÓN
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

        diferencia = validacion.get(
            "diferencia"
        )

        if diferencia is not None:

            print(
                (
                    "Diferencia: "
                    f"${diferencia:,.2f}"
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
    # MSI BBVA
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

    # ========================================================
    # CUOTAS MULTIBANCO
    # ========================================================

    (
        analisis_cuotas,
        conciliacion,
    ) = conciliar_cuotas_genericas(
        datos,
        conciliacion,
        analisis_regulares,
        mostrar=True,
    )

    # ========================================================
    # SIMULACIÓN / PREVALIDACIÓN DE CUOTAS
    # ========================================================

    analisis_alta_cuotas = (
        analizar_alta_cuotas_genericas(
            datos,
            analisis_cuotas,
            mostrar=True,
        )
    )

    resultado_cuotas = {
        "agregadas": 0,
        "duplicadas": 0,
        "conflictos": 0,
    }

    # ========================================================
    # 6C.4
    # APLICAR CUOTAS GENÉRICAS
    # ========================================================

    if aplicar:

        resultado_cuotas = (
            aplicar_cuotas_genericas(
                analisis_alta_cuotas
            )
        )

        if resultado_cuotas[
            "agregadas"
        ] > 0:

            print()

            print(
                "=== RECONCILIACIÓN DESPUÉS DE CUOTAS ==="
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

            (
                conciliacion,
                analisis_regulares,
                analisis_cuotas,
                proteccion_regulares,
            ) = recalcular_analisis_actual(
                datos,
                conciliacion,
                analisis_msi,
            )

        else:

            proteccion_regulares = (
                analizar_proteccion_regulares(
                    analisis_regulares
                )
            )

    else:

        proteccion_regulares = (
            mostrar_proteccion_regulares(
                analisis_regulares
            )
        )

    # ========================================================
    # EN MODO APLICAR MOSTRAR PROTECCIÓN ACTUALIZADA
    # ========================================================

    if aplicar:

        print()

        print(
            "=== CARGOS REGULARES ACTUALIZADOS ==="
        )

        print()

        print(
            (
                "Propuestos: "
                f"{len(proteccion_regulares['propuestas'])}"
            )
        )

        print(
            (
                "Listos para importar: "
                f"{len(proteccion_regulares['autoimportables'])}"
            )
        )

        print(
            (
                "Conflictos por revisar: "
                f"{len(proteccion_regulares['requieren_revision'])}"
            )
        )

    # ========================================================
    # REGULARES NUEVOS
    # ========================================================

    resultado_regulares = {
        "agregadas": 0,
        "duplicadas": 0,
        "conflictos": 0,
    }

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

            (
                conciliacion,
                analisis_regulares,
                analisis_cuotas,
                proteccion_regulares,
            ) = recalcular_analisis_actual(
                datos,
                conciliacion,
                analisis_msi,
            )

            mostrar_resumen_conciliacion(
                conciliacion
            )

    # ========================================================
    # DIFERENCIAS
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
        len(
            invalidos_msi
        ) > 0
        or
        resultado_msi[
            "conflictos"
        ] > 0
    )

    # ========================================================
    # SEGURIDAD CUOTAS GENÉRICAS
    # ========================================================

    cuotas_faltantes = (
        analisis_cuotas.get(
            "faltantes",
            [],
        )
    )

    cuotas_ambiguas = (
        analisis_cuotas.get(
            "ambiguas",
            [],
        )
    )

    hay_cuotas_sin_resolver = (
        len(
            cuotas_faltantes
        ) > 0
        or
        len(
            cuotas_ambiguas
        ) > 0
    )

    hay_conflicto_cuotas = (
        resultado_cuotas[
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
        and not hay_cuotas_sin_resolver
        and not hay_conflicto_cuotas
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

        if hay_cuotas_sin_resolver:

            print(
                (
                    "Cuotas faltantes: "
                    f"{len(cuotas_faltantes)}"
                )
            )

            print(
                (
                    "Cuotas ambiguas: "
                    f"{len(cuotas_ambiguas)}"
                )
            )

        if hay_conflicto_cuotas:

            print(
                (
                    "Conflictos de cuotas: "
                    f"{resultado_cuotas['conflictos']}"
                )
            )

        if hay_revision_regulares:

            print(
                (
                    "Conflictos regulares: "
                    f"{len(proteccion_regulares['requieren_revision'])}"
                )
            )

    # ========================================================
    # ESTADOS DE CUENTA
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
    # ESTADO EXISTENTE
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

    if len(
        rutas
    ) != 1:

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
        rutas[
            0
        ],
        aplicar=aplicar,
    )


if __name__ == "__main__":
    main()