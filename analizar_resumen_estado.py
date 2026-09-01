import sys

from lector_estados import (
    extraer_texto_pdf,
    extraer_datos_estado,
    extraer_resumen_cargos_abonos,
    extraer_movimientos_regulares_invex,
    clasificar_abonos_estado,
    sumar_movimientos,
)


# ============================================================
# MOSTRAR MONTOS
# ============================================================

def mostrar_monto(
    etiqueta,
    monto,
    signo=""
):

    if monto is None:

        print(
            f"{etiqueta:<29} NO DETECTADO"
        )

        return

    print(
        (
            f"{etiqueta:<29} "
            f"{signo}${monto:,.2f}"
        )
    )


# ============================================================
# MOSTRAR MOVIMIENTOS
# ============================================================

def mostrar_movimientos(
    titulo,
    movimientos
):

    print()
    print(
        titulo
    )

    print(
        "-" * 50
    )

    if not movimientos:

        print(
            "Ninguno."
        )

        return

    for movimiento in movimientos:

        print(
            (
                f"${movimiento['monto']:,.2f} "
                f"| {movimiento['descripcion']} "
                f"| {movimiento['fecha_operacion']}"
            )
        )


# ============================================================
# DETERMINAR ABONOS QUE REDUCEN EL PAGO REQUERIDO
# ============================================================

def calcular_abonos_aplicables(
    cuenta,
    pagos_reales,
    aclaraciones,
    devoluciones,
    otros_abonos
):

    # --------------------------------------------------------
    # INVEX
    # --------------------------------------------------------
    #
    # En el estado probado:
    #
    # ACL PROCEDENTE aparece como abono,
    # pero NO reduce el pago para no generar intereses.
    #
    # Solo usamos pagos reales.
    # --------------------------------------------------------

    if cuenta == "Invex":

        return round(
            pagos_reales,
            2
        )

    # --------------------------------------------------------
    # BANAMEX
    # --------------------------------------------------------
    #
    # Tanto pagos como devoluciones/créditos
    # reducen el saldo requerido.
    # --------------------------------------------------------

    if cuenta in (
        "Citibanamex Costco",
        "Citibanamex Oro",
    ):

        return round(
            pagos_reales
            + aclaraciones
            + devoluciones
            + otros_abonos,
            2
        )

    # --------------------------------------------------------
    # BBVA
    # --------------------------------------------------------
    #
    # Pagos y devoluciones detectadas
    # reducen el saldo del periodo.
    # --------------------------------------------------------

    if cuenta == "BBVA Platinum":

        return round(
            pagos_reales
            + aclaraciones
            + devoluciones
            + otros_abonos,
            2
        )

    return round(
        pagos_reales,
        2
    )


# ============================================================
# ANALIZAR ESTADO
# ============================================================

def analizar_estado(
    ruta_pdf
):

    # ========================================================
    # LEER PDF
    # ========================================================

    datos = extraer_datos_estado(
        ruta_pdf
    )

    texto = extraer_texto_pdf(
        ruta_pdf
    )

    resumen = extraer_resumen_cargos_abonos(
        texto
    )

    cuenta = datos.get(
        "cuenta"
    )

    # ========================================================
    # MOVIMIENTOS
    # ========================================================

    movimientos_banco = (
        extraer_movimientos_regulares_invex(
            texto
        )
    )

    # ========================================================
    # CLASIFICACIÓN SEGÚN BANCO
    # ========================================================

    abonos = clasificar_abonos_estado(
        movimientos_banco,
        cuenta
    )

    pagos_reales_lista = abonos.get(
        "pagos_reales",
        []
    )

    aclaraciones_lista = abonos.get(
        "aclaraciones",
        []
    )

    devoluciones_lista = abonos.get(
        "devoluciones",
        []
    )

    otros_abonos_lista = abonos.get(
        "otros_abonos",
        []
    )

    # ========================================================
    # TOTALES DE ABONOS
    # ========================================================

    total_pagos_reales = sumar_movimientos(
        pagos_reales_lista
    )

    total_aclaraciones = sumar_movimientos(
        aclaraciones_lista
    )

    total_devoluciones = sumar_movimientos(
        devoluciones_lista
    )

    total_otros_abonos = sumar_movimientos(
        otros_abonos_lista
    )

    total_clasificado = round(
        total_pagos_reales
        + total_aclaraciones
        + total_devoluciones
        + total_otros_abonos,
        2
    )

    total_banco_abonos = resumen.get(
        "pagos_abonos"
    )

    # ========================================================
    # ABONOS QUE SÍ REDUCEN EL PAGO REQUERIDO
    # ========================================================

    abonos_aplicables = (
        calcular_abonos_aplicables(
            cuenta,
            total_pagos_reales,
            total_aclaraciones,
            total_devoluciones,
            total_otros_abonos
        )
    )

    # ========================================================
    # ENCABEZADO
    # ========================================================

    print()
    print(
        "=" * 40
    )

    print(
        "📊 RESUMEN FINANCIERO DEL ESTADO"
    )

    print(
        "=" * 40
    )

    print()

    print(
        f"Cuenta: {cuenta}"
    )

    print(
        f"Periodo: {datos.get('periodo')}"
    )

    print(
        (
            "Fecha de corte: "
            f"{datos.get('fecha_corte')}"
        )
    )

    print(
        (
            "Fecha límite de pago: "
            f"{datos.get('fecha_limite_pago')}"
        )
    )

    # ========================================================
    # RESUMEN DEL BANCO
    # ========================================================

    print()
    print(
        "=== RESUMEN DEL BANCO ==="
    )

    print()

    mostrar_monto(
        "Adeudo anterior:",
        resumen.get(
            "adeudo_anterior"
        )
    )

    mostrar_monto(
        "Cargos regulares:",
        resumen.get(
            "cargos_regulares"
        ),
        "+"
    )

    mostrar_monto(
        "Cargos a meses:",
        resumen.get(
            "cargos_meses"
        ),
        "+"
    )

    mostrar_monto(
        "Intereses:",
        resumen.get(
            "intereses"
        ),
        "+"
    )

    mostrar_monto(
        "Comisiones:",
        resumen.get(
            "comisiones"
        ),
        "+"
    )

    mostrar_monto(
        "IVA:",
        resumen.get(
            "iva"
        ),
        "+"
    )

    mostrar_monto(
        "Pagos y abonos banco:",
        total_banco_abonos,
        "-"
    )

    # ========================================================
    # CLASIFICACIÓN
    # ========================================================

    print()
    print(
        "=== CLASIFICACIÓN DE ABONOS ==="
    )

    print()

    mostrar_monto(
        "Pagos reales:",
        total_pagos_reales,
        "-"
    )

    mostrar_monto(
        "Aclaraciones:",
        total_aclaraciones,
        "-"
    )

    mostrar_monto(
        "Devoluciones / créditos:",
        total_devoluciones,
        "-"
    )

    mostrar_monto(
        "Otros abonos:",
        total_otros_abonos,
        "-"
    )

    # ========================================================
    # VALIDACIÓN DE CLASIFICACIÓN
    # ========================================================

    print()
    print(
        "=== VALIDACIÓN DE ABONOS ==="
    )

    print()

    if total_banco_abonos is not None:

        diferencia_abonos = round(
            total_banco_abonos
            - total_clasificado,
            2
        )

        mostrar_monto(
            "Banco reporta:",
            total_banco_abonos
        )

        mostrar_monto(
            "Clasificado por Python:",
            total_clasificado
        )

        mostrar_monto(
            "Diferencia abonos:",
            diferencia_abonos
        )

        if abs(
            diferencia_abonos
        ) <= 0.01:

            print(
                (
                    "✅ Los abonos están "
                    "completamente clasificados."
                )
            )

        else:

            print(
                (
                    "⚠️ Hay abonos que todavía "
                    "no fueron identificados."
                )
            )

    # ========================================================
    # CÁLCULO DEL PAGO REQUERIDO
    # ========================================================

    print()
    print(
        "=" * 40
    )

    print(
        "🧮 CÁLCULO DEL PAGO REQUERIDO"
    )

    print(
        "=" * 40
    )

    print()

    componentes = [
        resumen.get(
            "adeudo_anterior"
        ),
        resumen.get(
            "cargos_regulares"
        ),
        resumen.get(
            "cargos_meses"
        ),
        resumen.get(
            "intereses"
        ),
        resumen.get(
            "comisiones"
        ),
        resumen.get(
            "iva"
        ),
    ]

    if not all(
        valor is not None
        for valor in componentes
    ):

        print(
            (
                "⚠️ No pude extraer todos "
                "los componentes necesarios."
            )
        )

        return

    mostrar_monto(
        "Adeudo anterior:",
        resumen[
            "adeudo_anterior"
        ]
    )

    mostrar_monto(
        "Cargos regulares:",
        resumen[
            "cargos_regulares"
        ],
        "+"
    )

    mostrar_monto(
        "Cargos a meses:",
        resumen[
            "cargos_meses"
        ],
        "+"
    )

    mostrar_monto(
        "Intereses:",
        resumen[
            "intereses"
        ],
        "+"
    )

    mostrar_monto(
        "Comisiones:",
        resumen[
            "comisiones"
        ],
        "+"
    )

    mostrar_monto(
        "IVA:",
        resumen[
            "iva"
        ],
        "+"
    )

    mostrar_monto(
        "Abonos aplicables:",
        abonos_aplicables,
        "-"
    )

    # ========================================================
    # ECUACIÓN
    # ========================================================

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
        2
    )

    pago_estado = resumen.get(
        "pago_no_intereses"
    )

    if pago_estado is None:

        pago_estado = datos.get(
            "pago_para_no_generar_intereses"
        )

    diferencia = round(
        pago_estado
        - calculado,
        2
    )

    print()
    print(
        "-" * 50
    )

    mostrar_monto(
        "Calculado:",
        calculado
    )

    mostrar_monto(
        "Pago estado:",
        pago_estado
    )

    mostrar_monto(
        "Diferencia:",
        diferencia
    )

    print()

    if abs(
        diferencia
    ) <= 0.01:

        print(
            "✅ EL ESTADO CUADRA"
        )

    else:

        print(
            "⚠️ EL ESTADO NO CUADRA"
        )

    # ========================================================
    # DETALLE
    # ========================================================

    mostrar_movimientos(
        "💵 PAGOS REALES",
        pagos_reales_lista
    )

    mostrar_movimientos(
        "↩️ ACLARACIONES / REEMBOLSOS",
        aclaraciones_lista
    )

    mostrar_movimientos(
        "🔄 DEVOLUCIONES / CRÉDITOS",
        devoluciones_lista
    )

    mostrar_movimientos(
        "❓ OTROS ABONOS",
        otros_abonos_lista
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
                "python analizar_resumen_estado.py "
                "\"estados/archivo.pdf\""
            )
        )

        return

    analizar_estado(
        sys.argv[
            1
        ]
    )


if __name__ == "__main__":

    main()