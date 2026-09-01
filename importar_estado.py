import sys

from lector_estados import (
    extraer_datos_estado
)

from sheets import (
    obtener_estados_cuenta,
    obtener_movimientos,
    registrar_estado_cuenta
)

from finanzas import (
    calcular_total_fecha_pago,
    convertir_fecha
)


# ============================================================
# BUSCAR ESTADO DUPLICADO
# ============================================================

def estado_ya_importado(
    estados_existentes,
    cuenta,
    periodo
):

    cuenta_normalizada = (
        str(
            cuenta
        )
        .strip()
        .lower()
    )

    periodo_normalizado = (
        str(
            periodo
        )
        .strip()
        .lower()
    )

    for estado in estados_existentes:

        cuenta_estado = (
            str(
                estado.get(
                    "Cuenta",
                    ""
                )
            )
            .strip()
            .lower()
        )

        periodo_estado = (
            str(
                estado.get(
                    "Periodo",
                    ""
                )
            )
            .strip()
            .lower()
        )

        if (
            cuenta_estado
            == cuenta_normalizada
            and periodo_estado
            == periodo_normalizado
        ):

            return True

    return False


# ============================================================
# VALIDAR DATOS EXTRAÍDOS
# ============================================================

def validar_datos_estado(
    datos
):

    faltantes = []

    if datos.get(
        "cuenta"
    ) is None:

        faltantes.append(
            "cuenta"
        )

    if datos.get(
        "periodo"
    ) is None:

        faltantes.append(
            "periodo"
        )

    if datos.get(
        "fecha_corte"
    ) is None:

        faltantes.append(
            "fecha de corte"
        )

    if datos.get(
        "fecha_limite_pago"
    ) is None:

        faltantes.append(
            "fecha límite de pago"
        )

    if datos.get(
        "pago_para_no_generar_intereses"
    ) is None:

        faltantes.append(
            "pago para no generar intereses"
        )

    if faltantes:

        raise ValueError(
            (
                "No pude extraer del PDF: "
                + ", ".join(
                    faltantes
                )
            )
        )


# ============================================================
# IMPORTAR ESTADO
# ============================================================

def importar_estado(
    ruta_pdf
):

    # ========================================================
    # LEER PDF
    # ========================================================

    datos = extraer_datos_estado(
        ruta_pdf
    )

    # ========================================================
    # VALIDAR
    # ========================================================

    validar_datos_estado(
        datos
    )

    cuenta = datos[
        "cuenta"
    ]

    periodo = datos[
        "periodo"
    ]

    fecha_corte = datos[
        "fecha_corte"
    ]

    fecha_limite = datos[
        "fecha_limite_pago"
    ]

    banco = datos[
        "pago_para_no_generar_intereses"
    ]

    # ========================================================
    # EVITAR DUPLICADOS
    # ========================================================

    estados_existentes = (
        obtener_estados_cuenta()
    )

    if estado_ya_importado(
        estados_existentes,
        cuenta,
        periodo
    ):

        print()

        print(
            "⚠️ Este estado ya fue importado."
        )

        print()

        print(
            f"Cuenta: {cuenta}"
        )

        print(
            f"Periodo: {periodo}"
        )

        print()

        return

    # ========================================================
    # OBTENER MOVIMIENTOS
    # ========================================================

    movimientos = obtener_movimientos()

    # ========================================================
    # CONVERTIR FECHA LÍMITE
    # ========================================================

    fecha_limite_objeto = (
        convertir_fecha(
            fecha_limite
        )
    )

    # ========================================================
    # CALCULAR CAPTURADO
    # ========================================================

    capturado = (
        calcular_total_fecha_pago(
            movimientos,
            cuenta,
            fecha_limite_objeto
        )
    )

    capturado = round(
        capturado,
        2
    )

    # ========================================================
    # DIFERENCIA
    # ========================================================

    diferencia = round(
        banco
        - capturado,
        2
    )

    # ========================================================
    # STATUS
    # ========================================================

    if abs(
        diferencia
    ) <= 0.01:

        status = (
            "Conciliado"
        )

    else:

        status = (
            "Revisar"
        )

    # ========================================================
    # REGISTRAR EN ESTADOSCUENTA
    # ========================================================

    fila = [
        cuenta,
        periodo,
        fecha_corte,
        fecha_limite,
        banco,
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
        "========================================"
    )

    print(
        "📄 ESTADO IMPORTADO"
    )

    print(
        "========================================"
    )

    print()

    print(
        f"Cuenta: {cuenta}"
    )

    print(
        f"Periodo: {periodo}"
    )

    print(
        f"Fecha de corte: {fecha_corte}"
    )

    print(
        f"Fecha límite: {fecha_limite}"
    )

    print()

    print(
        (
            "Banco:      "
            f"${banco:,.2f}"
        )
    )

    print(
        (
            "Capturado:  "
            f"${capturado:,.2f}"
        )
    )

    print(
        (
            "Diferencia: "
            f"${diferencia:,.2f}"
        )
    )

    print()

    # ========================================================
    # RESULTADO DE CONCILIACIÓN
    # ========================================================

    if status == "Conciliado":

        print(
            "✅ CONCILIADO"
        )

    elif diferencia > 0:

        print(
            (
                "⚠️ REVISAR: faltan "
                f"${diferencia:,.2f} "
                "por identificar."
            )
        )

    else:

        print(
            (
                "⚠️ REVISAR: tienes "
                f"${abs(diferencia):,.2f} "
                "capturados de más."
            )
        )

    print()


# ============================================================
# MAIN
# ============================================================

def main():

    if len(
        sys.argv
    ) < 2:

        print()

        print(
            "Uso:"
        )

        print(
            (
                "python importar_estado.py "
                "\"estados/archivo.pdf\""
            )
        )

        print()

        return

    ruta_pdf = sys.argv[
        1
    ]

    try:

        importar_estado(
            ruta_pdf
        )

    except Exception as error:

        print()

        print(
            "❌ Error importando estado:"
        )

        print(
            str(
                error
            )
        )

        print()


if __name__ == "__main__":

    main()