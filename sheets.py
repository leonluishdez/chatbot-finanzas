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

    return obtener_hoja().get_all_records()


def registrar_movimiento(
    fila
):

    obtener_hoja().append_row(
        fila,
        value_input_option="USER_ENTERED"
    )


def registrar_movimientos(
    filas
):

    if not filas:
        return

    obtener_hoja().append_rows(
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

    if "Subcategoria" not in encabezados:
        raise RuntimeError(
            "No existe la columna Subcategoria "
            "en la hoja Movimientos."
        )

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

        subcategoria = str(
            movimiento.get(
                "Subcategoria",
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

    if "Subcategoria" not in encabezados:
        raise RuntimeError(
            "No existe la columna Subcategoria "
            "en la hoja Movimientos."
        )

    columna_subcategoria = (
        encabezados.index(
            "Subcategoria"
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

    obtener_hoja_estados_cuenta().append_row(
        fila,
        value_input_option="USER_ENTERED"
    )


def registrar_estados_cuenta(
    filas
):

    if not filas:
        return

    obtener_hoja_estados_cuenta().append_rows(
        filas,
        value_input_option="USER_ENTERED"
    )
