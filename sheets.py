from datetime import datetime
from finanzas import convertir_fecha
import json
import os
from functools import lru_cache

import gspread


# ============================================================
# CONFIGURACIÓN
# ============================================================

NOMBRE_ARCHIVO = os.getenv(
    "GOOGLE_SHEET_NAME",
    "Sistema Financiero Personal"
)

NOMBRE_HOJA = os.getenv(
    "GOOGLE_WORKSHEET_NAME",
    "Movimientos"
)

NOMBRE_HOJA_ESTADOS = os.getenv(
    "GOOGLE_WORKSHEET_ESTADOS_NAME",
    "EstadosCuenta"
)

ARCHIVO_CREDENCIALES = "service_account.json"

# "Rubro" es el nombre visible actual de la columna H. Conservamos la
# compatibilidad con "Subcategoria" para hojas y pruebas anteriores.
COLUMNAS_RUBRO = ("Rubro", "Subcategoria")


# ============================================================
# CLIENTE DE GOOGLE SHEETS
# ============================================================

def obtener_cliente():

    credenciales_json = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_JSON"
    )

    # Railway / producción
    if credenciales_json:

        credenciales = json.loads(
            credenciales_json
        )

        return gspread.service_account_from_dict(
            credenciales
        )

    # Desarrollo local
    if os.path.exists(
        ARCHIVO_CREDENCIALES
    ):

        return gspread.service_account(
            filename=ARCHIVO_CREDENCIALES
        )

    raise RuntimeError(
        "No se encontraron credenciales "
        "de Google Sheets."
    )


# ============================================================
# ARCHIVO
# ============================================================

@lru_cache(maxsize=1)
def obtener_archivo():

    cliente = obtener_cliente()

    return cliente.open(
        NOMBRE_ARCHIVO
    )


# ============================================================
# HOJA: MOVIMIENTOS
# ============================================================

@lru_cache(maxsize=1)
def obtener_hoja():

    return obtener_archivo().worksheet(
        NOMBRE_HOJA
    )


def obtener_movimientos():
    movimientos = obtener_hoja().get_all_records()

    # El resto de la aplicación todavía usa la llave interna Subcategoria.
    # Al exponer este alias no se pierde compatibilidad si la hoja ya se
    # renombró a Rubro.
    for movimiento in movimientos:
        if "Rubro" in movimiento and "Subcategoria" not in movimiento:
            movimiento["Subcategoria"] = movimiento["Rubro"]

    return movimientos


def obtener_columna_rubro(encabezados):

    for columna in COLUMNAS_RUBRO:
        if columna in encabezados:
            return columna

    raise RuntimeError(
        "No existe la columna Rubro (antes Subcategoria) "
        "en la hoja Movimientos."
    )


def registrar_movimiento(
    fila
):

    hoja = obtener_hoja()
    fila = preparar_fechas_fila(fila, (1, 2))
    hoja.format("B:C", {"numberFormat": {"type": "DATE", "pattern": "dd/m/yy"}})
    hoja.append_row(
        fila,
        value_input_option="USER_ENTERED"
    )


def registrar_movimientos(
    filas
):

    if not filas:
        return

    hoja = obtener_hoja()
    filas = [preparar_fechas_fila(fila, (1, 2)) for fila in filas]
    hoja.format("B:C", {"numberFormat": {"type": "DATE", "pattern": "dd/m/yy"}})
    hoja.append_rows(
        filas,
        value_input_option="USER_ENTERED"
    )


# ============================================================
# MOVIMIENTOS SIN CLASIFICAR
# ============================================================

def obtener_movimientos_sin_clasificar():

    hoja = obtener_hoja()
    valores = hoja.get_all_values()

    if not valores:
        return []

    encabezados = [
        str(valor).strip()
        for valor in valores[0]
    ]

    columna_rubro = obtener_columna_rubro(encabezados)

    pendientes = []

    for numero_fila, fila in enumerate(
        valores[1:],
        start=2
    ):

        movimiento = {}

        for indice, encabezado in enumerate(
            encabezados
        ):

            if indice < len(fila):
                valor = fila[indice]
            else:
                valor = ""

            movimiento[
                encabezado
            ] = valor

        if columna_rubro == "Rubro":
            movimiento["Subcategoria"] = movimiento.get("Rubro", "")

        subcategoria = str(
            movimiento.get(
                columna_rubro,
                ""
            )
        ).strip().lower()

        tipo_movimiento = str(
            movimiento.get(
                "Tipo de Movimiento",
                ""
            )
        ).strip().lower()

        if (
            subcategoria == "sin clasificar"
            and tipo_movimiento == "gasto"
        ):

            movimiento[
                "_fila"
            ] = numero_fila

            pendientes.append(
                movimiento
            )

    return pendientes


def actualizar_subcategoria_movimiento(
    numero_fila,
    nueva_subcategoria
):

    if not nueva_subcategoria:
        raise ValueError(
            "La subcategoría no puede estar vacía."
        )

    try:
        numero_fila = int(
            numero_fila
        )
    except (
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            "El número de fila no es válido."
        ) from error

    if numero_fila < 2:
        raise ValueError(
            "No se puede modificar la fila de encabezados."
        )

    hoja = obtener_hoja()
    encabezados = hoja.row_values(
        1
    )

    columna_rubro = obtener_columna_rubro(encabezados)

    columna_subcategoria = (
        encabezados.index(
            columna_rubro
        )
        + 1
    )

    subcategoria_actual = str(
        hoja.cell(
            numero_fila,
            columna_subcategoria
        ).value
        or ""
    ).strip()

    if (
        subcategoria_actual.lower()
        != "sin clasificar"
    ):

        return False

    hoja.update_cell(
        numero_fila,
        columna_subcategoria,
        nueva_subcategoria
    )

    return True


# ============================================================
# HOJA: ESTADOS DE CUENTA
# ============================================================

@lru_cache(maxsize=1)
def obtener_hoja_estados_cuenta():

    return obtener_archivo().worksheet(
        NOMBRE_HOJA_ESTADOS
    )


def obtener_estados_cuenta():

    return (
        obtener_hoja_estados_cuenta()
        .get_all_records()
    )


def registrar_estado_cuenta(
    fila
):

    hoja = obtener_hoja_estados_cuenta()
    fila = preparar_fechas_fila(fila, (2, 3))
    hoja.format("C:D", {"numberFormat": {"type": "DATE", "pattern": "dd/m/yy"}})
    hoja.append_row(
        fila,
        value_input_option="USER_ENTERED"
    )


def registrar_estados_cuenta(
    filas
):

    if not filas:
        return

    hoja = obtener_hoja_estados_cuenta()
    filas = [preparar_fechas_fila(fila, (2, 3)) for fila in filas]
    hoja.format("C:D", {"numberFormat": {"type": "DATE", "pattern": "dd/m/yy"}})
    hoja.append_rows(
        filas,
        value_input_option="USER_ENTERED"
    )


def preparar_fechas_fila(fila, indices):
    """Fechas nativas de Sheets sin depender de su configuración regional.

    El formato visual se aplica antes de escribir. Conserva vacíos y no muta
    la fila original. El resto de valores mantiene su tratamiento anterior.
    """
    resultado = list(fila)
    for indice in indices:
        valor = resultado[indice]
        if valor is None or str(valor).strip() == "":
            continue
        fecha = convertir_fecha(valor)
        resultado[indice] = (datetime(fecha.year, fecha.month, fecha.day) - datetime(1899, 12, 30)).days
    return resultado
