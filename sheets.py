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