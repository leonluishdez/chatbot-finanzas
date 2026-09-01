from lector_estados import (
    extraer_datos_estado,
    extraer_texto_pdf,
    extraer_planes_msi_bbva,
)

from sheets import obtener_movimientos

from finanzas import (
    convertir_fecha,
    convertir_monto,
    normalizar_texto,
)


RUTA = "estados/BBVA Platinum agosto 2026.pdf"


def main():

    datos = extraer_datos_estado(
        RUTA
    )

    texto = extraer_texto_pdf(
        RUTA
    )

    planes = extraer_planes_msi_bbva(
        texto
    )

    movimientos = obtener_movimientos()

    fecha_limite = convertir_fecha(
        datos[
            "fecha_limite_pago"
        ]
    )

    print()
    print(
        "=" * 70
    )

    print(
        "🔎 COMPARACIÓN DE PLANES MSI BBVA VS SHEETS"
    )

    print(
        "=" * 70
    )

    encontrados = []
    faltantes = []

    for plan in planes:

        candidatos = []

        for movimiento in movimientos:

            cuenta = normalizar_texto(
                movimiento.get(
                    "Cuenta",
                    ""
                )
            )

            if cuenta != normalizar_texto(
                datos[
                    "cuenta"
                ]
            ):
                continue

            tipo_pago = normalizar_texto(
                movimiento.get(
                    "Tipo de Pago",
                    ""
                )
            )

            if tipo_pago != "meses":
                continue

            try:

                plazos = int(
                    movimiento.get(
                        "Numero de Plazos",
                        0
                    )
                )

            except (
                ValueError,
                TypeError
            ):
                continue

            if plazos != plan[
                "plazos"
            ]:
                continue

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
                continue

            if abs(
                monto
                - plan[
                    "cuota"
                ]
            ) > 0.01:
                continue

            try:

                fecha_pago = convertir_fecha(
                    movimiento.get(
                        "Fecha de Pago",
                        ""
                    )
                )

            except (
                ValueError,
                TypeError
            ):
                continue

            # La fecha exacta puede variar uno o
            # varios días frente a la fecha real
            # del estado.
            #
            # Para conciliación usamos el mismo
            # mes y año de pago.

            if (
                fecha_pago.month
                != fecha_limite.month
            ):
                continue

            if (
                fecha_pago.year
                != fecha_limite.year
            ):
                continue

            candidatos.append(
                movimiento
            )

        print()
        print(
            "-" * 70
        )

        print(
            (
                f"{plan['numero']:02d}/"
                f"{plan['plazos']:02d}"
                f" | cuota "
                f"${plan['cuota']:,.2f}"
                f" | original "
                f"${plan['monto_original']:,.2f}"
            )
        )

        print(
            plan[
                "descripcion"
            ]
        )

        if candidatos:

            movimiento = candidatos[
                0
            ]

            descripcion = (
                movimiento.get(
                    "Descripcion",
                    ""
                )
                or movimiento.get(
                    "Concepto",
                    ""
                )
            )

            print(
                "✅ ENCONTRADO EN SHEETS"
            )

            print(
                (
                    "   Descripción: "
                    f"{descripcion}"
                )
            )

            print(
                (
                    "   Fecha pago: "
                    f"{movimiento.get('Fecha de Pago', '')}"
                )
            )

            print(
                (
                    "   Monto: "
                    f"{movimiento.get('Monto de Compra', '')}"
                )
            )

            encontrados.append(
                {
                    "plan": plan,
                    "movimiento": movimiento,
                }
            )

        else:

            print(
                "❌ PLAN NO ENCONTRADO EN SHEETS"
            )

            faltantes.append(
                plan
            )

    print()
    print(
        "=" * 70
    )

    print(
        "📊 RESUMEN"
    )

    print(
        "=" * 70
    )

    print(
        (
            "Planes detectados: "
            f"{len(planes)}"
        )
    )

    print(
        (
            "Ya existentes: "
            f"{len(encontrados)}"
        )
    )

    print(
        (
            "Planes faltantes: "
            f"{len(faltantes)}"
        )
    )

    if faltantes:

        print()
        print(
            "💳 PLANES A RECONSTRUIR"
        )

        print(
            "-" * 70
        )

        for plan in faltantes:

            print(
                (
                    f"${plan['monto_original']:,.2f}"
                    f" | "
                    f"{plan['numero']}/"
                    f"{plan['plazos']}"
                    f" | cuota "
                    f"${plan['cuota']:,.2f}"
                    f" | "
                    f"{plan['descripcion']}"
                )
            )


if __name__ == "__main__":

    main()