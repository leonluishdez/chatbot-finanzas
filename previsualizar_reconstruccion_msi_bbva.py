from lector_estados import (
    extraer_datos_estado,
    extraer_texto_pdf,
    extraer_planes_msi_bbva,
    convertir_fecha_estado,
)

from sheets import obtener_movimientos

from finanzas import (
    generar_cuotas,
    convertir_fecha,
    convertir_monto,
    normalizar_texto,
)


RUTA = "estados/BBVA Platinum agosto 2026.pdf"


def plan_existe_en_periodo(
    plan,
    movimientos,
    cuenta,
    fecha_limite,
):

    for movimiento in movimientos:

        if normalizar_texto(
            movimiento.get(
                "Cuenta",
                ""
            )
        ) != normalizar_texto(
            cuenta
        ):
            continue

        if normalizar_texto(
            movimiento.get(
                "Tipo de Pago",
                ""
            )
        ) != "meses":
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

        if (
            fecha_pago.month
            == fecha_limite.month
            and fecha_pago.year
            == fecha_limite.year
        ):

            return True

    return False


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

    cuenta = datos[
        "cuenta"
    ]

    fecha_limite = convertir_fecha(
        datos[
            "fecha_limite_pago"
        ]
    )

    faltantes = []

    for plan in planes:

        existe = plan_existe_en_periodo(
            plan,
            movimientos,
            cuenta,
            fecha_limite,
        )

        if not existe:

            faltantes.append(
                plan
            )

    print()
    print(
        "=" * 72
    )

    print(
        "🧩 RECONSTRUCCIÓN DE PLANES MSI FALTANTES"
    )

    print(
        "=" * 72
    )

    print()

    print(
        f"Planes faltantes: {len(faltantes)}"
    )

    for plan in faltantes:

        print()
        print(
            "=" * 72
        )

        print(
            (
                f"💳 {plan['descripcion']}"
            )
        )

        print(
            "=" * 72
        )

        print(
            (
                "Monto original: "
                f"${plan['monto_original']:,.2f}"
            )
        )

        print(
            (
                "Plan: "
                f"{plan['plazos']} MSI"
            )
        )

        print(
            (
                "Cuota actual banco: "
                f"{plan['numero']}/"
                f"{plan['plazos']} "
                f"| ${plan['cuota']:,.2f}"
            )
        )

        fecha_compra = convertir_fecha_estado(
            plan[
                "fecha_compra"
            ]
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

        print()
        print(
            "CUOTAS QUE DEBERÍAN EXISTIR"
        )

        print(
            "-" * 72
        )

        total = 0

        for cuota in cuotas:

            total += cuota[
                "monto"
            ]

            es_actual = (
                cuota[
                    "numero"
                ]
                == plan[
                    "numero"
                ]
            )

            marca = (
                "👉"
                if es_actual
                else "  "
            )

            fecha_texto = cuota[
                "fecha"
            ].strftime(
                "%d/%m/%Y"
            )

            print(
                (
                    f"{marca} "
                    f"{cuota['numero']:02d}/"
                    f"{plan['plazos']:02d}"
                    f" | {fecha_texto}"
                    f" | ${cuota['monto']:,.2f}"
                )
            )

        print()
        print(
            (
                "Total reconstruido: "
                f"${total:,.2f}"
            )
        )

        diferencia = round(
            total
            - plan[
                "monto_original"
            ],
            2
        )

        print(
            (
                "Diferencia vs original: "
                f"${diferencia:,.2f}"
            )
        )

        cuota_actual = cuotas[
            plan[
                "numero"
            ]
            - 1
        ]

        print()

        print(
            "VALIDACIÓN CONTRA EL ESTADO"
        )

        print(
            "-" * 72
        )

        print(
            (
                "Cuota reconstruida: "
                f"${cuota_actual['monto']:,.2f}"
            )
        )

        print(
            (
                "Cuota banco:        "
                f"${plan['cuota']:,.2f}"
            )
        )

        diferencia_cuota = round(
            cuota_actual[
                "monto"
            ]
            - plan[
                "cuota"
            ],
            2
        )

        print(
            (
                "Diferencia:          "
                f"${diferencia_cuota:,.2f}"
            )
        )

        if abs(
            diferencia_cuota
        ) <= 0.01:

            print(
                "✅ PLAN RECONSTRUIDO CORRECTAMENTE"
            )

        else:

            print(
                "❌ EL PLAN NO COINCIDE CON BBVA"
            )


if __name__ == "__main__":

    main()