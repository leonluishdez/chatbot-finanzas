import re

from lector_estados import (
    extraer_datos_estado,
    extraer_texto_pdf,
    extraer_movimientos_regulares_invex,
)

from sheets import obtener_movimientos

from finanzas import (
    convertir_fecha,
    obtener_movimientos_fecha_pago,
)

from conciliar_movimientos import (
    preparar_movimientos_internos,
    comparar_movimientos,
    clasificar_movimiento_banco,
)


RUTA = "estados/BBVA Platinum agosto 2026.pdf"


def detectar_msi(descripcion):

    descripcion = str(
        descripcion
    ).upper()

    patron = re.search(
        r"\b(\d+)\s+DE\s+(\d+)\b",
        descripcion
    )

    if not patron:

        return None

    return {
        "numero": int(
            patron.group(1)
        ),
        "plazos": int(
            patron.group(2)
        ),
    }


def main():

    datos = extraer_datos_estado(
        RUTA
    )

    texto = extraer_texto_pdf(
        RUTA
    )

    movimientos_banco = (
        extraer_movimientos_regulares_invex(
            texto
        )
    )

    movimientos = obtener_movimientos()

    fecha_limite = convertir_fecha(
        datos[
            "fecha_limite_pago"
        ]
    )

    movimientos_periodo = (
        obtener_movimientos_fecha_pago(
            movimientos,
            datos[
                "cuenta"
            ],
            fecha_limite,
        )
    )

    internos = (
        preparar_movimientos_internos(
            movimientos_periodo
        )
    )

    resultado = comparar_movimientos(
        movimientos_banco,
        internos,
    )

    faltantes = resultado[
        "solo_banco"
    ]

    regulares = []
    msi = []

    for movimiento in faltantes:

        if clasificar_movimiento_banco(
            movimiento
        ) != "cargo":

            continue

        info_msi = detectar_msi(
            movimiento[
                "descripcion"
            ]
        )

        if info_msi:

            msi.append(
                {
                    **movimiento,
                    **info_msi,
                }
            )

        else:

            regulares.append(
                movimiento
            )

    print()
    print(
        "=" * 65
    )

    print(
        "📋 PREVISUALIZACIÓN DE MOVIMIENTOS FALTANTES"
    )

    print(
        "=" * 65
    )

    print()

    print(
        "🛒 CARGOS REGULARES"
    )

    print(
        "-" * 65
    )

    for movimiento in regulares:

        print(
            (
                f"${movimiento['monto']:,.2f} "
                f"| {movimiento['descripcion']} "
                f"| {movimiento['fecha_operacion']}"
            )
        )

    print()

    total_regulares = round(
        sum(
            m[
                "monto"
            ]
            for m in regulares
        ),
        2
    )

    print(
        (
            f"Regulares: "
            f"{len(regulares)}"
        )
    )

    print(
        (
            f"Total regulares: "
            f"${total_regulares:,.2f}"
        )
    )

    print()
    print(
        "💳 PARCIALIDADES MSI"
    )

    print(
        "-" * 65
    )

    for movimiento in msi:

        print(
            (
                f"${movimiento['monto']:,.2f} "
                f"| "
                f"{movimiento['numero']}/"
                f"{movimiento['plazos']} "
                f"| "
                f"{movimiento['descripcion']}"
            )
        )

    print()

    total_msi = round(
        sum(
            m[
                "monto"
            ]
            for m in msi
        ),
        2
    )

    print(
        (
            f"MSI: "
            f"{len(msi)}"
        )
    )

    print(
        (
            f"Total MSI: "
            f"${total_msi:,.2f}"
        )
    )

    print()
    print(
        "=" * 65
    )

    print(
        (
            "TOTAL FALTANTE: "
            f"${total_regulares + total_msi:,.2f}"
        )
    )


if __name__ == "__main__":
    main()