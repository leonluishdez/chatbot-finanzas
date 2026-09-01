import sys

from lector_estados import (
    extraer_datos_estado,
    extraer_texto_pdf,
    extraer_resumen_cargos_abonos,
    extraer_movimientos_regulares_invex,
    clasificar_abonos_estado,
    sumar_movimientos,
)

from sheets import (
    obtener_movimientos,
    obtener_estados_cuenta,
    registrar_estado_cuenta,
)

from finanzas import (
    convertir_fecha,
    obtener_movimientos_fecha_pago,
)

from conciliar_movimientos import (
    preparar_movimientos_internos,
    comparar_movimientos,
)


# ============================================================
# ABONOS QUE REDUCEN EL PAGO REQUERIDO
# ============================================================

def calcular_abonos_aplicables(
    cuenta,
    pagos_reales,
    aclaraciones,
    devoluciones,
    otros_abonos,
):

    # INVEX:
    # Las aclaraciones procedentes detectadas
    # se conservan separadas y no se consideran
    # pagos reales para reconstruir el pago requerido.

    if cuenta == "Invex":

        return round(
            pagos_reales,
            2,
        )

    # BANAMEX y BBVA:
    # pagos + devoluciones + otros créditos
    # reducen el saldo del periodo.

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
# BUSCAR DUPLICADO
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
# VALIDAR MATEMÁTICAMENTE EL ESTADO
# ============================================================

def validar_estado(
    datos,
    resumen,
    movimientos_banco,
):

    cuenta = datos.get(
        "cuenta"
    )

    # --------------------------------------------------------
    # COMPONENTES OBLIGATORIOS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # CLASIFICAR ABONOS
    # --------------------------------------------------------

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

    if abs(
        diferencia_abonos
    ) > 0.01:

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

    # --------------------------------------------------------
    # ABONOS APLICABLES
    # --------------------------------------------------------

    abonos_aplicables = (
        calcular_abonos_aplicables(
            cuenta,
            pagos_reales,
            aclaraciones,
            devoluciones,
            otros_abonos,
        )
    )

    # --------------------------------------------------------
    # RECONSTRUIR PAGO REQUERIDO
    # --------------------------------------------------------

    calculado = round(
        resumen[
            "adeudo_anterior"
        ]
        + resumen[
            "cargos_regulares"
        ]
        + resumen[
            "cargos_meses"
        ]
        + resumen[
            "intereses"
        ]
        + resumen[
            "comisiones"
        ]
        + resumen[
            "iva"
        ]
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
            abs(
                diferencia
            ) <= 0.01
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
            item[
                "banco"
            ][
                "monto"
            ]
            for item
            in coincidencias
        ),
        2,
    )

    total_solo_banco = round(
        sum(
            movimiento[
                "monto"
            ]
            for movimiento
            in solo_banco
        ),
        2,
    )

    total_solo_interno = round(
        sum(
            movimiento[
                "monto"
            ]
            for movimiento
            in solo_interno
        ),
        2,
    )

    conciliado = (
        len(
            solo_banco
        ) == 0
        and len(
            solo_interno
        ) == 0
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
# IMPORTAR
# ============================================================

def importar_estado(
    ruta_pdf,
):

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
    # DATOS GENERALES OBLIGATORIOS
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
    # MOSTRAR IDENTIFICACIÓN
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
    # VALIDAR PDF
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
                )
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
                "El estado NO será "
                "registrado en Sheets."
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
    # CONCILIAR MOVIMIENTOS
    # ========================================================

    print()
    print(
        "=== CONCILIACIÓN CON MOVIMIENTOS ==="
    )

    conciliacion = (
        conciliar_con_sheets(
            datos,
            movimientos_banco,
        )
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

    # ========================================================
    # DETALLE DE DIFERENCIAS
    # ========================================================

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
                {}
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

    # ========================================================
    # STATUS
    # ========================================================

    if conciliacion[
        "conciliado"
    ]:

        status = "Conciliado"

        print()
        print(
            "✅ MOVIMIENTOS CONCILIADOS"
        )

    else:

        status = "Revisar"

        print()
        print(
            "⚠️ HAY MOVIMIENTOS POR REVISAR"
        )

    # ========================================================
    # EVITAR DUPLICADOS
    # ========================================================

    estados_existentes = (
        obtener_estados_cuenta()
    )

    existente = buscar_estado_existente(
        estados_existentes,
        cuenta,
        periodo,
    )

    if existente is not None:

        print()
        print(
            "⚠️ ESTADO YA REGISTRADO"
        )

        print(
            (
                f"{cuenta} | {periodo}"
            )
        )

        print(
            (
                "No se creó una fila "
                "duplicada."
            )
        )

        return

    # ========================================================
    # REGISTRAR
    # ========================================================

    fila = [
        cuenta,
        periodo,
        fecha_corte,
        fecha_limite,
        pago_estado,
        status,
    ]

    registrar_estado_cuenta(
        fila
    )

    # ========================================================
    # RESULTADO
    # ========================================================

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
        (
            "Status: "
            f"{status}"
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if len(
        sys.argv
    ) < 2:

        print(
            "Uso:"
        )

        print(
            (
                "python importar_estado.py "
                "\"estados/archivo.pdf\""
            )
        )

        return

    importar_estado(
        sys.argv[
            1
        ]
    )


if __name__ == "__main__":

    main()