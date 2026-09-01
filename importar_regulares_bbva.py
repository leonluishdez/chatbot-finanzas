import re
import sys
from datetime import datetime

from lector_estados import (
    extraer_datos_estado,
    extraer_texto_pdf,
    extraer_movimientos_regulares_invex,
)

from sheets import (
    obtener_movimientos,
    registrar_movimientos,
)

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


# ============================================================
# FECHA DEL BANCO
# ============================================================

def convertir_fecha_banco(
    valor
):

    dia, mes, anio = (
        valor.lower().split("-")
    )

    return datetime(
        int(anio),
        MESES[mes],
        int(dia),
    )


# ============================================================
# LIMPIAR DESCRIPCIÓN
# ============================================================

def limpiar_descripcion(
    descripcion
):

    descripcion = re.sub(
        (
            r"\s*;\s*"
            r"Tarjeta Digital\s+"
            r"\*+\d+\s*$"
        ),
        "",
        descripcion,
        flags=re.IGNORECASE,
    )

    return descripcion.strip()


# ============================================================
# CATEGORÍA
# ============================================================

def sugerir_categoria(
    descripcion
):

    texto = descripcion.lower()

    # --------------------------------------------------------
    # Transporte
    # --------------------------------------------------------

    if any(
        palabra in texto
        for palabra in [
            "uber ride",
            "uber rides",
            "didi rides",
            "super didi",
        ]
    ):

        return "Transporte"

    # --------------------------------------------------------
    # Salud
    # --------------------------------------------------------

    if any(
        palabra in texto
        for palabra in [
            "farm guadalajara",
            "tda nat",
            "allianz pl retail",
            "sanrafael",
        ]
    ):

        return "Salud"

    # --------------------------------------------------------
    # Servicios
    # --------------------------------------------------------

    if any(
        palabra in texto
        for palabra in [
            "at t",
            "at&t",
        ]
    ):

        return "Servicios"

    # --------------------------------------------------------
    # Entretenimiento
    # --------------------------------------------------------

    if "cinepolis" in texto:

        return "Entretenimiento"

    # --------------------------------------------------------
    # Comida
    # --------------------------------------------------------

    if any(
        palabra in texto
        for palabra in [
            "oxxo",
            "abts",
            "city market",
            "rest ",
            "cafe",
            "didifood",
            "walmart",
        ]
    ):

        return "Comida"

    # --------------------------------------------------------
    # Casos confirmados como Varios
    # --------------------------------------------------------

    if any(
        palabra in texto
        for palabra in [
            "bbw plaza patria",
            "bout spf",
        ]
    ):

        return "Varios"

    return "Varios"


# ============================================================
# OBTENER FALTANTES
# ============================================================

def obtener_regulares_faltantes():

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

    return (
        datos,
        movimientos_banco,
        regulares,
    )


# ============================================================
# CREAR FILAS
# ============================================================

def crear_filas(
    datos,
    regulares,
):

    fecha_pago = convertir_fecha(
        datos[
            "fecha_limite_pago"
        ]
    ).strftime(
        "%d/%m/%Y"
    )

    filas = []

    for movimiento in regulares:

        descripcion = limpiar_descripcion(
            movimiento[
                "descripcion"
            ]
        )

        categoria = sugerir_categoria(
            descripcion
        )

        fecha_compra = (
            convertir_fecha_banco(
                movimiento[
                    "fecha_operacion"
                ]
            )
            .strftime(
                "%d/%m/%Y"
            )
        )

        fila = [
            "Gasto",               # Tipo de Movimiento
            fecha_pago,            # Fecha de Pago
            fecha_compra,          # Fecha de Compra
            movimiento["monto"],   # Monto de Compra
            datos["cuenta"],       # Cuenta
            "",                    # Concepto
            descripcion,           # Descripcion
            categoria,             # Subcategoria
            "Contado",             # Tipo de Pago
            1,                     # Numero de Plazos
            "Pendiente",           # Status
        ]

        filas.append(
            {
                "fila": fila,
                "movimiento": movimiento,
                "descripcion": descripcion,
                "categoria": categoria,
            }
        )

    return filas


# ============================================================
# VERIFICACIÓN POSTERIOR
# ============================================================

def verificar_conciliacion(
    datos,
    movimientos_banco,
):

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

    total_coincidente = round(
        sum(
            item[
                "banco"
            ][
                "monto"
            ]
            for item
            in resultado[
                "coincidencias"
            ]
        ),
        2
    )

    total_solo_banco = round(
        sum(
            movimiento[
                "monto"
            ]
            for movimiento
            in resultado[
                "solo_banco"
            ]
        ),
        2
    )

    total_solo_sheets = round(
        sum(
            movimiento[
                "monto"
            ]
            for movimiento
            in resultado[
                "solo_interno"
            ]
        ),
        2
    )

    print()
    print(
        "=" * 70
    )

    print(
        "🔍 VERIFICACIÓN POSTERIOR"
    )

    print(
        "=" * 70
    )

    print()

    print(
        "Coincidencias:",
        len(
            resultado[
                "coincidencias"
            ]
        )
    )

    print(
        "Solo banco:",
        len(
            resultado[
                "solo_banco"
            ]
        )
    )

    print(
        "Solo Sheets:",
        len(
            resultado[
                "solo_interno"
            ]
        )
    )

    print()

    print(
        (
            "Coincidente: "
            f"${total_coincidente:,.2f}"
        )
    )

    print(
        (
            "Solo banco:  "
            f"${total_solo_banco:,.2f}"
        )
    )

    print(
        (
            "Solo Sheets: "
            f"${total_solo_sheets:,.2f}"
        )
    )

    print()

    if (
        len(
            resultado[
                "solo_banco"
            ]
        ) == 0
        and len(
            resultado[
                "solo_interno"
            ]
        ) == 0
    ):

        print(
            "✅ ESTADO COMPLETAMENTE CONCILIADO"
        )

    else:

        print(
            "⚠️ TODAVÍA HAY DIFERENCIAS"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    aplicar = (
        "--aplicar"
        in sys.argv
    )

    (
        datos,
        movimientos_banco,
        regulares,
    ) = obtener_regulares_faltantes()

    filas = crear_filas(
        datos,
        regulares,
    )

    print()
    print(
        "=" * 78
    )

    if aplicar:

        print(
            "🔧 IMPORTACIÓN DE CARGOS REGULARES BBVA"
        )

    else:

        print(
            "🔍 SIMULACIÓN DE IMPORTACIÓN BBVA"
        )

    print(
        "=" * 78
    )

    print()

    total = 0

    for numero, item in enumerate(
        filas,
        start=1
    ):

        movimiento = item[
            "movimiento"
        ]

        total += movimiento[
            "monto"
        ]

        print(
            (
                f"{numero:02d}. "
                f"${movimiento['monto']:,.2f}"
                f" | "
                f"{item['descripcion']}"
                f" | "
                f"{item['categoria']}"
            )
        )

    print()
    print(
        "-" * 78
    )

    print(
        "Movimientos a registrar:",
        len(
            filas
        )
    )

    print(
        (
            "Total: "
            f"${total:,.2f}"
        )
    )

    # --------------------------------------------------------
    # SIMULACIÓN
    # --------------------------------------------------------

    if not aplicar:

        print()
        print(
            "ℹ️ Google Sheets NO fue modificado."
        )

        print()
        print(
            "Para aplicar:"
        )

        print(
            (
                "python importar_regulares_bbva.py "
                "--aplicar"
            )
        )

        return

    # --------------------------------------------------------
    # NO HAY NADA QUE IMPORTAR
    # --------------------------------------------------------

    if not filas:

        print()
        print(
            "✅ No existen cargos regulares pendientes."
        )

        return

    # --------------------------------------------------------
    # REGISTRAR
    # --------------------------------------------------------

    filas_sheets = [
        item[
            "fila"
        ]
        for item
        in filas
    ]

    registrar_movimientos(
        filas_sheets
    )

    print()
    print(
        "✅ MOVIMIENTOS REGISTRADOS"
    )

    print(
        (
            "Filas agregadas: "
            f"{len(filas_sheets)}"
        )
    )

    # --------------------------------------------------------
    # VOLVER A CONCILIAR
    # --------------------------------------------------------

    verificar_conciliacion(
        datos,
        movimientos_banco,
    )


if __name__ == "__main__":

    main()