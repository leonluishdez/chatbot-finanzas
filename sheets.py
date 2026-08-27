import json
import os

from functools import lru_cache

import gspread


NOMBRE_ARCHIVO = os.getenv(
    "GOOGLE_SHEET_NAME",
    "Sistema Financiero Personal"
)

NOMBRE_HOJA = os.getenv(
    "GOOGLE_WORKSHEET_NAME",
    "Movimientos"
)

ARCHIVO_CREDENCIALES = (
    "service_account.json"
)


def obtener_cliente():

    credenciales_json = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_JSON"
    )

    # =========================
    # RAILWAY / PRODUCCIÓN
    # =========================

    if credenciales_json:

        credenciales = json.loads(
            credenciales_json
        )

        return (
            gspread.service_account_from_dict(
                credenciales
            )
        )

    # =========================
    # LOCAL
    # =========================

    if os.path.exists(
        ARCHIVO_CREDENCIALES
    ):

        return gspread.service_account(
            filename=ARCHIVO_CREDENCIALES
        )

    raise RuntimeError(
        "No se encontraron credenciales de Google Sheets."
    )


@lru_cache(maxsize=1)
def obtener_hoja():

    cliente = obtener_cliente()

    archivo = cliente.open(
        NOMBRE_ARCHIVO
    )

    return archivo.worksheet(
        NOMBRE_HOJA
    )


def obtener_movimientos():

    hoja = obtener_hoja()

    return hoja.get_all_records()


def registrar_movimiento(fila):

    hoja = obtener_hoja()

    hoja.append_row(
        fila,
        value_input_option="USER_ENTERED"
    )


def registrar_movimientos(filas):

    if not filas:
        return

    hoja = obtener_hoja()

    hoja.append_rows(
        filas,
        value_input_option="USER_ENTERED"
    )