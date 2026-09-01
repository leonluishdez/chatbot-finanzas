import re
from datetime import datetime

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


MESES = {
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


def convertir_fecha_banco(valor):

    dia, mes, anio = valor.lower().split("-")

    return datetime(
        int(anio),
        MESES[mes],
        int(dia),
    )


def limpiar_descripcion(descripcion):

    descripcion = re.sub(
        r"\s*;\s*Tarjeta Digital\s+\*+\d+\s*$",
        "",
        descripcion,
        flags=re.IGNORECASE,
    )

    return descripcion.strip()


def sugerir_categoria(descripcion):

    texto = descripcion.lower()

    # Transporte
    if any(
        palabra in texto
        for palabra in [
            "uber ride",
            "uber rides",
            "didi rides",
            "super didi",
        ]
    ):
        return "Transporte", "alta"

    # Comida
    if any(
        palabra in texto
        for palabra in [
            "oxxo",
            "abts",
            "city market",
            "rest ",
            "cafe",
            "didifood",
        ]
    ):
        return "Comida", "alta"

    # Salud
    if any(
        palabra in texto
        for palabra in [
            "farm guadalajara",
            "tda nat",
        ]
    ):
        return "Salud", "media"

    # Servicios
    if any(
        palabra in texto
        for palabra in [
            "at t",
            "at&t",
        ]
    ):
        return "Servicios", "alta"

    # Entretenimiento
    if "cinepolis" in texto:
        return "Entretenimiento", "alta"

        # Bath & Body Works
    if "bbw plaza patria" in texto:
        return "Varios", "alta"

    # Boutique SPF
    if "bout spf" in texto:
        return "Varios", "alta"

    # Seguro / servicio relacionado con salud
    if "allianz pl retail" in texto:
        return "Salud", "alta"

    # Supermercado
    if "walmart" in texto:
        return "Comida", "alta"

    # Gimnasio San Rafael
    if "sanrafael" in texto:
        return "Salud", "alta"

    # Ambiguos
    return "Varios", "revisar"


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

    internos = preparar_movimientos_internos(
        movimientos_periodo
    )

    resultado = comparar_movimientos(
        movimientos_banco,
        internos,
    )

    regulares = [
        movimiento
        for movimiento
        in resultado[
            "solo_banco"
        ]
        if clasificar_movimiento_banco(
            movimiento
        ) == "cargo"
    ]

    print()
    print("=" * 78)
    print("📋 PREVISUALIZACIÓN DE ALTA DE CARGOS REGULARES")
    print("=" * 78)

    print()
    print(
        "Cuenta:",
        datos["cuenta"]
    )

    print(
        "Fecha de pago:",
        datos["fecha_limite_pago"]
    )

    print()

    total = 0

    for numero, movimiento in enumerate(
        regulares,
        start=1
    ):

        descripcion = limpiar_descripcion(
            movimiento[
                "descripcion"
            ]
        )

        categoria, confianza = sugerir_categoria(
            descripcion
        )

        fecha_compra = convertir_fecha_banco(
            movimiento[
                "fecha_operacion"
            ]
        )

        total += movimiento[
            "monto"
        ]

        if confianza == "alta":
            marca = "✅"

        elif confianza == "media":
            marca = "🟡"

        else:
            marca = "⚠️"

        print(
            f"{numero:02d}. {marca} "
            f"${movimiento['monto']:,.2f}"
            f" | {descripcion}"
        )

        print(
            f"    Compra: "
            f"{fecha_compra.strftime('%d/%m/%Y')}"
        )

        print(
            f"    Categoría sugerida: "
            f"{categoria}"
        )

        print()

    print("-" * 78)

    print(
        f"Movimientos: {len(regulares)}"
    )

    print(
        f"Total: ${total:,.2f}"
    )

    print()

    print(
        "✅ = clasificación bastante clara"
    )

    print(
        "🟡 = razonable, pero merece revisión"
    )

    print(
        "⚠️ = se dejaría en Varios hasta revisarlo"
    )


if __name__ == "__main__":
    main()