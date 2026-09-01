import sys
from datetime import datetime

from lector_estados import (
    extraer_texto_pdf,
    extraer_planes_msi_bbva,
)

from sheets import (
    obtener_movimientos,
    registrar_movimientos,
)

from finanzas import (
    generar_cuotas,
    convertir_monto,
    normalizar_texto,
)


RUTA = "estados/BBVA Platinum agosto 2026.pdf"
CUENTA = "BBVA Platinum"


# ============================================================
# FECHA DEL ESTADO → DATETIME
# ============================================================

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


def convertir_fecha_plan(valor):

    partes = valor.lower().split("-")

    if len(partes) != 3:
        raise ValueError(
            f"Fecha no reconocida: {valor}"
        )

    dia = int(partes[0])
    mes = MESES[partes[1]]
    anio = int(partes[2])

    return datetime(
        anio,
        mes,
        dia,
    )


# ============================================================
# VERIFICAR SI EL PLAN YA EXISTE
# ============================================================

def plan_ya_existe(
    plan,
    movimientos,
):

    for movimiento in movimientos:

        if normalizar_texto(
            movimiento.get(
                "Cuenta",
                ""
            )
        ) != normalizar_texto(
            CUENTA
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
            TypeError,
        ):
            continue

        if plazos != plan["plazos"]:
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
            TypeError,
        ):
            continue

        # Buscamos la cuota normal del plan.
        if abs(
            monto - plan["cuota"]
        ) <= 0.01:
            return True

    return False


# ============================================================
# DESCRIPCIÓN AMIGABLE
# ============================================================

def obtener_nombre_plan(plan):

    descripcion = normalizar_texto(
        plan["descripcion"]
    )

    if (
        "amazon"
        in descripcion
        and plan["plazos"] == 6
        and abs(
            plan["monto_original"]
            - 1959
        ) <= 0.01
    ):
        return "Amazon 6 MSI"

    if (
        "mercado pago"
        in descripcion
        and plan["plazos"] == 3
        and abs(
            plan["monto_original"]
            - 689
        ) <= 0.01
    ):
        return "Mercado Pago 3 MSI"

    return plan["descripcion"]


# ============================================================
# CREAR FILAS PARA SHEETS
# ============================================================

def crear_filas_plan(
    plan,
):

    fecha_compra = convertir_fecha_plan(
        plan["fecha_compra"]
    )

    nombre = obtener_nombre_plan(
        plan
    )

    cuotas = generar_cuotas(
        plan["monto_original"],
        plan["plazos"],
        fecha_compra,
        nombre,
        CUENTA,
    )

    filas = []

    for cuota in cuotas:

        fecha_pago = cuota[
            "fecha"
        ].strftime(
            "%d/%m/%Y"
        )

        fecha_compra_texto = (
            fecha_compra.strftime(
                "%d/%m/%Y"
            )
        )

        fila = [
            "Gasto",                   # Tipo de Movimiento
            fecha_pago,                # Fecha de Pago
            fecha_compra_texto,         # Fecha de Compra
            cuota["monto"],            # Monto de Compra
            CUENTA,                    # Cuenta
            "",                        # Concepto
            cuota["descripcion"],      # Descripcion
            "Varios",                  # Subcategoria
            "Meses",                   # Tipo de Pago
            plan["plazos"],            # Numero de Plazos
            (
                "Pagado"
                if cuota["numero"]
                < plan["numero"]
                else "Pendiente"
            ),                          # Status
        ]

        filas.append(
            {
                "fila": fila,
                "cuota": cuota,
            }
        )

    return filas


# ============================================================
# MAIN
# ============================================================

def main():

    aplicar = (
        "--aplicar"
        in sys.argv
    )

    texto = extraer_texto_pdf(
        RUTA
    )

    planes = extraer_planes_msi_bbva(
        texto
    )

    movimientos = obtener_movimientos()

    faltantes = [
        plan
        for plan in planes
        if not plan_ya_existe(
            plan,
            movimientos,
        )
    ]

    print()
    print(
        "=" * 72
    )

    if aplicar:
        print(
            "🔧 RECONSTRUCCIÓN MSI BBVA"
        )
    else:
        print(
            "🔍 SIMULACIÓN RECONSTRUCCIÓN MSI BBVA"
        )

    print(
        "=" * 72
    )

    print()
    print(
        f"Planes faltantes: {len(faltantes)}"
    )

    todas_las_filas = []

    for plan in faltantes:

        filas = crear_filas_plan(
            plan
        )

        todas_las_filas.extend(
            filas
        )

        print()
        print(
            "=" * 72
        )

        print(
            obtener_nombre_plan(
                plan
            )
        )

        print(
            "=" * 72
        )

        print(
            "Monto original:",
            f"${plan['monto_original']:,.2f}"
        )

        print(
            "Plan:",
            f"{plan['plazos']} MSI"
        )

        print(
            "Cuota actual:",
            (
                f"{plan['numero']}/"
                f"{plan['plazos']}"
            )
        )

        print()

        for item in filas:

            cuota = item[
                "cuota"
            ]

            status = item[
                "fila"
            ][10]

            marca = (
                "👉"
                if cuota["numero"]
                == plan["numero"]
                else "  "
            )

            print(
                (
                    f"{marca} "
                    f"{cuota['numero']:02d}/"
                    f"{plan['plazos']:02d}"
                    f" | "
                    f"{cuota['fecha'].strftime('%d/%m/%Y')}"
                    f" | "
                    f"${cuota['monto']:,.2f}"
                    f" | "
                    f"{status}"
                )
            )

        total = sum(
            item["cuota"]["monto"]
            for item in filas
        )

        print()
        print(
            "Total:",
            f"${total:,.2f}"
        )

        print(
            "Original:",
            f"${plan['monto_original']:,.2f}"
        )

        diferencia = round(
            total
            - plan["monto_original"],
            2
        )

        print(
            "Diferencia:",
            f"${diferencia:,.2f}"
        )

    print()
    print(
        "=" * 72
    )

    print(
        "Filas nuevas:",
        len(todas_las_filas)
    )

    print(
        "=" * 72
    )

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
                "python "
                "reconstruir_msi_faltantes_bbva.py "
                "--aplicar"
            )
        )

        return

    if not todas_las_filas:

        print()
        print(
            "✅ No hay planes pendientes."
        )

        return

    filas_para_sheets = [
        item["fila"]
        for item in todas_las_filas
    ]

    registrar_movimientos(
        filas_para_sheets
    )

    print()
    print(
        "✅ PLANES MSI REGISTRADOS"
    )

    print(
        f"Filas agregadas: {len(filas_para_sheets)}"
    )


if __name__ == "__main__":
    main()