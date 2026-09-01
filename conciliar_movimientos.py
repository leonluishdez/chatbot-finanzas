import sys

from difflib import SequenceMatcher

from lector_estados import (
    extraer_datos_estado,
    extraer_movimientos_regulares_invex,
    extraer_texto_pdf
)

from sheets import (
    obtener_movimientos
)

from finanzas import (
    convertir_fecha,
    convertir_monto,
    normalizar_texto,
    obtener_movimientos_fecha_pago
)


# ============================================================
# DESCRIPCIÓN INTERNA
# ============================================================

def obtener_descripcion_interna(
    movimiento
):

    descripcion = str(
        movimiento.get(
            "Descripcion",
            ""
        )
    ).strip()

    if descripcion:

        return descripcion

    concepto = str(
        movimiento.get(
            "Concepto",
            ""
        )
    ).strip()

    if concepto:

        return concepto

    return "Sin descripción"


# ============================================================
# SIMILITUD DE DESCRIPCIONES
# ============================================================

def calcular_similitud(
    texto_a,
    texto_b
):

    texto_a = normalizar_texto(
        texto_a
    )

    texto_b = normalizar_texto(
        texto_b
    )

    return SequenceMatcher(
        None,
        texto_a,
        texto_b
    ).ratio()


# ============================================================
# PREPARAR MOVIMIENTOS INTERNOS
# ============================================================

def preparar_movimientos_internos(
    movimientos
):

    preparados = []

    for movimiento in movimientos:

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

        preparados.append(
            {
                "descripcion": (
                    obtener_descripcion_interna(
                        movimiento
                    )
                ),
                "monto": round(
                    monto,
                    2
                ),
                "movimiento": movimiento,
            }
        )

    return preparados


# ============================================================
# COMPARAR MOVIMIENTOS
# ============================================================

def comparar_movimientos(
    movimientos_banco,
    movimientos_internos,
    tolerancia=0.20
):

    coincidencias = []

    solo_banco = []

    usados_internos = set()

    cargos_banco = [
        movimiento

        for movimiento in movimientos_banco

        if movimiento[
            "monto"
        ] > 0
    ]

    for movimiento_banco in cargos_banco:

        monto_banco = movimiento_banco[
            "monto"
        ]

        candidatos = []

        for indice, movimiento_interno in enumerate(
            movimientos_internos
        ):

            if indice in usados_internos:
                continue

            monto_interno = movimiento_interno[
                "monto"
            ]

            diferencia_monto = round(
                abs(
                    monto_banco
                    - monto_interno
                ),
                2
            )

            # Permitimos pequeñas diferencias
            # de centavos.
            if diferencia_monto <= tolerancia:

                similitud = calcular_similitud(
                    movimiento_banco[
                        "descripcion"
                    ],
                    movimiento_interno[
                        "descripcion"
                    ]
                )

                candidatos.append(
                    {
                        "indice": indice,
                        "interno": (
                            movimiento_interno
                        ),
                        "diferencia_monto": (
                            diferencia_monto
                        ),
                        "similitud": (
                            similitud
                        ),
                    }
                )

        if not candidatos:

            solo_banco.append(
                movimiento_banco
            )

            continue

        # Primero gana el monto más cercano.
        # Si hay empate, usamos descripción.
        candidatos.sort(
            key=lambda candidato: (
                candidato[
                    "diferencia_monto"
                ],
                -candidato[
                    "similitud"
                ],
            )
        )

        mejor = candidatos[
            0
        ]

        indice_elegido = mejor[
            "indice"
        ]

        usados_internos.add(
            indice_elegido
        )

        coincidencias.append(
            {
                "banco": movimiento_banco,

                "interno": mejor[
                    "interno"
                ],

                "similitud": mejor[
                    "similitud"
                ],

                "diferencia_monto": mejor[
                    "diferencia_monto"
                ],
            }
        )

    solo_interno = []

    for indice, movimiento in enumerate(
        movimientos_internos
    ):

        if indice not in usados_internos:

            solo_interno.append(
                movimiento
            )

    return {
        "coincidencias": coincidencias,
        "solo_banco": solo_banco,
        "solo_interno": solo_interno,
    }


# ============================================================
# MOSTRAR RESULTADO
# ============================================================

def imprimir_resultado(
    datos_estado,
    resultado
):

    cuenta = datos_estado.get(
        "cuenta"
    )

    periodo = datos_estado.get(
        "periodo"
    )

    banco_total = datos_estado.get(
        "pago_para_no_generar_intereses"
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

    print()
    print(
        "========================================"
    )

    print(
        "🔍 CONCILIACIÓN MOVIMIENTO A MOVIMIENTO"
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

    print()

    # ========================================================
    # COINCIDENCIAS
    # ========================================================

    print(
        "✅ COINCIDENCIAS"
    )

    print()

    if not coincidencias:

        print(
            "Ninguna."
        )

    for coincidencia in coincidencias:

        banco = coincidencia[
            "banco"
        ]

        interno = coincidencia[
            "interno"
        ]

        diferencia_monto = coincidencia.get(
            "diferencia_monto",
            0
        )

        similitud = coincidencia.get(
            "similitud",
            0
        )

        if diferencia_monto <= 0.01:

            simbolo = "✅"

        else:

            simbolo = "≈"

        print(
            (
                f"{simbolo} "
                f"${banco['monto']:,.2f} "
                f"| Banco: "
                f"{banco['descripcion']}"
            )
        )

        print(
            (
                "           "
                f"Sheets: "
                f"${interno['monto']:,.2f} "
                f"| {interno['descripcion']}"
            )
        )

        if diferencia_monto > 0.01:

            print(
                (
                    "           "
                    "Diferencia de monto: "
                    f"${diferencia_monto:,.2f}"
                )
            )

        if similitud < 0.20:

            print(
                (
                    "           "
                    "⚠️ Descripciones muy distintas"
                )
            )

        print()

    # ========================================================
    # SOLO BANCO
    # ========================================================

    print(
        "⚠️ SOLO EN EL BANCO"
    )

    print()

    if not solo_banco:

        print(
            "Ninguno."
        )

    for movimiento in solo_banco:

        print(
            (
                f"${movimiento['monto']:,.2f} "
                f"| "
                f"{movimiento['descripcion']}"
            )
        )

    print()

    # ========================================================
    # SOLO SHEETS
    # ========================================================

    print(
        "🟡 SOLO EN SHEETS"
    )

    print()

    if not solo_interno:

        print(
            "Ninguno."
        )

    for movimiento in solo_interno:

        print(
            (
                f"${movimiento['monto']:,.2f} "
                f"| "
                f"{movimiento['descripcion']}"
            )
        )

    # ========================================================
    # TOTALES DE COMPARACIÓN
    # ========================================================

    suma_coincidente = round(
        sum(
            item[
                "banco"
            ][
                "monto"
            ]

            for item in coincidencias
        ),
        2
    )

    suma_solo_banco = round(
        sum(
            movimiento[
                "monto"
            ]

            for movimiento in solo_banco
        ),
        2
    )

    suma_solo_interno = round(
        sum(
            movimiento[
                "monto"
            ]

            for movimiento in solo_interno
        ),
        2
    )

    print()
    print(
        "----------------------------------------"
    )

    print(
        (
            "Coincidente:    "
            f"${suma_coincidente:,.2f}"
        )
    )

    print(
        (
            "Solo banco:     "
            f"${suma_solo_banco:,.2f}"
        )
    )

    print(
        (
            "Solo Sheets:    "
            f"${suma_solo_interno:,.2f}"
        )
    )

    if banco_total is not None:

        print(
            (
                "Pago estado:    "
                f"${banco_total:,.2f}"
            )
        )

    print(
        "----------------------------------------"
    )


# ============================================================
# CONCILIAR PDF
# ============================================================

def conciliar_pdf(
    ruta_pdf
):

    # ========================================================
    # DATOS GENERALES
    # ========================================================

    datos_estado = extraer_datos_estado(
        ruta_pdf
    )

    cuenta = datos_estado.get(
        "cuenta"
    )

    fecha_limite = datos_estado.get(
        "fecha_limite_pago"
    )

    if cuenta is None:

        raise ValueError(
            "No pude detectar la cuenta."
        )

    if fecha_limite is None:

        raise ValueError(
            (
                "No pude detectar "
                "la fecha límite."
            )
        )

    # ========================================================
    # MOVIMIENTOS DEL PDF
    # ========================================================

    texto_pdf = extraer_texto_pdf(
        ruta_pdf
    )

    movimientos_banco = (
        extraer_movimientos_regulares_invex(
            texto_pdf
        )
    )

    # ========================================================
    # MOVIMIENTOS DE SHEETS
    # ========================================================

    todos_movimientos = (
        obtener_movimientos()
    )

    fecha_limite_objeto = convertir_fecha(
        fecha_limite
    )

    movimientos_periodo = (
        obtener_movimientos_fecha_pago(
            todos_movimientos,
            cuenta,
            fecha_limite_objeto
        )
    )

    movimientos_internos = (
        preparar_movimientos_internos(
            movimientos_periodo
        )
    )

    # ========================================================
    # COMPARAR
    # ========================================================

    resultado = comparar_movimientos(
        movimientos_banco,
        movimientos_internos
    )

    imprimir_resultado(
        datos_estado,
        resultado
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if len(
        sys.argv
    ) < 2:

        print(
            (
                "Uso: "
                "python conciliar_movimientos.py "
                "\"estados/archivo.pdf\""
            )
        )

        return

    ruta_pdf = sys.argv[
        1
    ]

    conciliar_pdf(
        ruta_pdf
    )


if __name__ == "__main__":

    main()