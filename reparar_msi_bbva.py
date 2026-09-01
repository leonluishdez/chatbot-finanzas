import sys

from sheets import obtener_hoja

from finanzas import (
    convertir_fecha,
    convertir_monto,
    dividir_monto_en_plazos,
)


CUENTA = "BBVA Platinum"

MONTO_ORIGINAL = 5802.60

PLAZOS = 15

FECHA_PRIMERA = convertir_fecha(
    "3/11/25"
)

FECHA_ULTIMA = convertir_fecha(
    "3/1/27"
)


def buscar_airpods():

    hoja = obtener_hoja()

    valores = hoja.get_all_values()

    if not valores:

        raise RuntimeError(
            "La hoja Movimientos está vacía."
        )

    encabezados = valores[0]

    columnas = {
        nombre: indice
        for indice, nombre
        in enumerate(encabezados)
    }

    requeridas = [
        "Monto de Compra",
        "Cuenta",
        "Descripcion",
        "Tipo de Pago",
        "Numero de Plazos",
        "Fecha de Pago",
    ]

    faltantes = [
        columna
        for columna in requeridas
        if columna not in columnas
    ]

    if faltantes:

        raise RuntimeError(
            (
                "Faltan columnas: "
                + ", ".join(faltantes)
            )
        )

    resultados = []

    # Empezamos en fila 2 porque
    # la fila 1 contiene encabezados.

    for numero_fila, fila in enumerate(
        valores[1:],
        start=2
    ):

        def valor(nombre):

            indice = columnas[
                nombre
            ]

            if indice >= len(fila):
                return ""

            return fila[
                indice
            ]

        cuenta = valor(
            "Cuenta"
        ).strip()

        tipo_pago = valor(
            "Tipo de Pago"
        ).strip().lower()

        numero_plazos = valor(
            "Numero de Plazos"
        ).strip()

        if cuenta != CUENTA:
            continue

        if tipo_pago != "meses":
            continue

        if numero_plazos != str(
            PLAZOS
        ):
            continue

        try:

            monto = convertir_monto(
                valor(
                    "Monto de Compra"
                )
            )

            fecha = convertir_fecha(
                valor(
                    "Fecha de Pago"
                )
            )

        except (
            ValueError,
            TypeError
        ):
            continue

        # Las mensualidades históricas de AirPods
        # están alrededor de $387.
        #
        # Esto evita tomar las mensualidades
        # del colchón de $314.

        if not (
            386 <= monto <= 388
        ):
            continue

        if fecha < FECHA_PRIMERA:
            continue

        if fecha > FECHA_ULTIMA:
            continue

        resultados.append(
            {
                "fila": numero_fila,
                "fecha": fecha,
                "fecha_texto": valor(
                    "Fecha de Pago"
                ),
                "monto": monto,
                "descripcion": valor(
                    "Descripcion"
                ),
            }
        )

    resultados.sort(
        key=lambda item: item[
            "fecha"
        ]
    )

    return (
        hoja,
        columnas,
        resultados,
    )


def main():

    aplicar = (
        "--aplicar"
        in sys.argv
    )

    (
        hoja,
        columnas,
        movimientos,
    ) = buscar_airpods()

    if len(
        movimientos
    ) != PLAZOS:

        print()
        print(
            "❌ REPARACIÓN CANCELADA"
        )

        print(
            (
                "Esperaba encontrar "
                f"{PLAZOS} mensualidades "
                "de AirPods."
            )
        )

        print(
            (
                "Encontradas: "
                f"{len(movimientos)}"
            )
        )

        return

    total_actual = round(
        sum(
            movimiento[
                "monto"
            ]
            for movimiento
            in movimientos
        ),
        2
    )

    if abs(
        total_actual
        - MONTO_ORIGINAL
    ) > 0.01:

        print()
        print(
            "❌ REPARACIÓN CANCELADA"
        )

        print(
            (
                "El total encontrado no "
                "coincide con el monto original."
            )
        )

        print(
            (
                f"Encontrado: "
                f"${total_actual:,.2f}"
            )
        )

        print(
            (
                f"Esperado: "
                f"${MONTO_ORIGINAL:,.2f}"
            )
        )

        return

    montos_correctos = (
        dividir_monto_en_plazos(
            MONTO_ORIGINAL,
            PLAZOS,
            CUENTA
        )
    )

    print()
    print(
        "=" * 60
    )

    if aplicar:

        print(
            "🔧 REPARACIÓN MSI BBVA"
        )

    else:

        print(
            "🔍 SIMULACIÓN MSI BBVA"
        )

    print(
        "=" * 60
    )

    print()

    cambios = []

    for numero, (
        movimiento,
        monto_correcto
    ) in enumerate(
        zip(
            movimientos,
            montos_correctos
        ),
        start=1
    ):

        monto_actual = movimiento[
            "monto"
        ]

        diferencia = round(
            monto_correcto
            - monto_actual,
            2
        )

        if abs(
            diferencia
        ) <= 0.001:

            marca = "✅"

        else:

            marca = "🔧"

            cambios.append(
                {
                    "fila": movimiento[
                        "fila"
                    ],
                    "monto_actual": (
                        monto_actual
                    ),
                    "monto_nuevo": (
                        monto_correcto
                    ),
                    "numero": numero,
                }
            )

        print(
            (
                f"{marca} "
                f"{numero:02d}/{PLAZOS} "
                f"| fila "
                f"{movimiento['fila']} "
                f"| "
                f"{movimiento['fecha_texto']} "
                f"| "
                f"${monto_actual:,.2f} "
                f"→ "
                f"${monto_correcto:,.2f}"
            )
        )

    print()
    print(
        (
            "Total actual:   "
            f"${total_actual:,.2f}"
        )
    )

    print(
        (
            "Total corregido: "
            f"${sum(montos_correctos):,.2f}"
        )
    )

    print(
        (
            "Filas a cambiar: "
            f"{len(cambios)}"
        )
    )

    # ========================================================
    # SOLO SIMULACIÓN
    # ========================================================

    if not aplicar:

        print()
        print(
            "ℹ️ No se modificó Google Sheets."
        )

        print(
            (
                "Para aplicar estos cambios:"
            )
        )

        print()
        print(
            (
                "python reparar_msi_bbva.py "
                "--aplicar"
            )
        )

        return

    # ========================================================
    # APLICAR CAMBIOS
    # ========================================================

    columna_monto = (
        columnas[
            "Monto de Compra"
        ]
        + 1
    )

    for cambio in cambios:

        hoja.update_cell(
            cambio[
                "fila"
            ],
            columna_monto,
            cambio[
                "monto_nuevo"
            ]
        )

        print(
            (
                "✅ Fila "
                f"{cambio['fila']}: "
                f"${cambio['monto_actual']:,.2f} "
                "→ "
                f"${cambio['monto_nuevo']:,.2f}"
            )
        )

    print()
    print(
        "✅ REPARACIÓN TERMINADA"
    )


if __name__ == "__main__":

    main()