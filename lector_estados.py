import json
import re
import sys
import unicodedata
from pathlib import Path

from pypdf import PdfReader


# ============================================================
# MESES
# ============================================================

MESES_ESTADO = {
    "ene": 1,
    "enero": 1,

    "feb": 2,
    "febrero": 2,

    "mar": 3,
    "marzo": 3,

    "abr": 4,
    "abril": 4,

    "may": 5,
    "mayo": 5,

    "jun": 6,
    "junio": 6,

    "jul": 7,
    "julio": 7,

    "ago": 8,
    "agosto": 8,

    "sep": 9,
    "sept": 9,
    "septiembre": 9,

    "oct": 10,
    "octubre": 10,

    "nov": 11,
    "noviembre": 11,

    "dic": 12,
    "diciembre": 12,
}


NOMBRES_MESES_ESTADO = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


# ============================================================
# NORMALIZACIÓN
# ============================================================

def normalizar_texto(
    texto
):

    texto = str(
        texto
    ).lower()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    return "".join(
        caracter
        for caracter in texto
        if unicodedata.category(
            caracter
        ) != "Mn"
    )


# ============================================================
# LEER PDF
# ============================================================

def extraer_texto_pdf(
    ruta_pdf,
    password=None
):

    ruta = Path(
        ruta_pdf
    )

    if not ruta.exists():

        raise FileNotFoundError(
            f"No existe el archivo: {ruta}"
        )

    reader = PdfReader(
        str(ruta)
    )

    if reader.is_encrypted:

        resultado = reader.decrypt(
            password or ""
        )

        if not resultado:

            raise ValueError(
                (
                    "El PDF está protegido "
                    "con contraseña."
                )
            )

    textos = []

    # Leemos TODAS las páginas.
    # Antes solo leíamos las primeras,
    # pero ahora necesitamos movimientos
    # y resúmenes completos.
    for pagina in reader.pages:

        texto = (
            pagina.extract_text()
            or ""
        )

        textos.append(
            texto
        )

    return "\n".join(
        textos
    )


# ============================================================
# CONVERTIR FECHA DEL ESTADO
# ============================================================

def convertir_fecha_estado(
    fecha_texto
):

    fecha_normalizada = normalizar_texto(
        fecha_texto.strip()
    )

    match = re.fullmatch(
        (
            r"(\d{1,2})-"
            r"([a-z]+)-"
            r"(\d{4})"
        ),
        fecha_normalizada
    )

    if match is None:

        raise ValueError(
            (
                "Fecha del estado no reconocida: "
                f"{fecha_texto}"
            )
        )

    dia = int(
        match.group(1)
    )

    nombre_mes = match.group(
        2
    )

    anio = int(
        match.group(3)
    )

    if nombre_mes in MESES_ESTADO:

        mes = MESES_ESTADO[
            nombre_mes
        ]

    else:

        abreviatura = nombre_mes[
            :3
        ]

        mes = MESES_ESTADO.get(
            abreviatura
        )

    if mes is None:

        raise ValueError(
            (
                "Mes no reconocido: "
                f"{nombre_mes}"
            )
        )

    return {
        "dia": dia,
        "mes": mes,
        "anio": anio,
    }


# ============================================================
# DETECTAR CUENTA
# ============================================================

def detectar_cuenta_estado(
    texto
):

    texto_normalizado = normalizar_texto(
        texto
    )

    if (
        "costco banamex"
        in texto_normalizado
    ):

        return "Citibanamex Costco"

    if (
        "oro banamex"
        in texto_normalizado
    ):

        return "Citibanamex Oro"

    if "invex" in texto_normalizado:

        return "Invex"

    if (
        "bbva" in texto_normalizado
        and "platinum"
        in texto_normalizado
    ):

        return "BBVA Platinum"

    return None


# ============================================================
# FECHA DE CORTE
# ============================================================

def extraer_fecha_corte(
    texto
):

    patron_fecha = (
        r"(\d{1,2}-"
        r"[A-Za-zÁÉÍÓÚáéíóú]+-"
        r"\d{4})"
    )

    # Intento directo:
    # Fecha de corte: 12-ago-2026

    match = re.search(
        (
            r"Fecha de corte:"
            r"\s*"
            + patron_fecha
        ),
        texto,
        re.IGNORECASE
    )

    if match:

        return match.group(
            1
        )

    # INVEX a veces pone las etiquetas
    # primero y las fechas después.
    #
    # Usamos entonces el final del periodo:
    #
    # 13-Jul-2026 al 12-Ago-2026

    match_periodo = re.search(
        (
            patron_fecha
            + r"\s+al\s+"
            + patron_fecha
        ),
        texto,
        re.IGNORECASE
    )

    if match_periodo:

        return match_periodo.group(
            2
        )

    return None


# ============================================================
# FECHA LÍMITE
# ============================================================

def extraer_fecha_limite(
    texto
):

    patron_fecha = (
        r"(\d{1,2}-"
        r"[A-Za-zÁÉÍÓÚáéíóú]+-"
        r"\d{4})"
    )

    match = re.search(
        (
            r"Fecha l[ií]mite de pago:"
            r"\s*\d*"
            r"\s*"
            r"(?:[^\n,]*,\s*)?"
            + patron_fecha
        ),
        texto,
        re.IGNORECASE
    )

    if match is None:

        return None

    return match.group(
        1
    )


# ============================================================
# PAGO PARA NO GENERAR INTERESES
# ============================================================

def extraer_pago_no_intereses(
    texto
):

    texto_limpio = re.sub(
        r"\s+",
        " ",
        texto
    )

    match = re.search(
        (
            r"Pago para no generar intereses:"
            r"\s*\d*"
            r"\s*\$"
            r"\s*"
            r"([\d,]+(?:\.\d{2})?)"
        ),
        texto_limpio,
        re.IGNORECASE
    )

    if match is None:

        return None

    monto_texto = (
        match.group(1)
        .replace(
            ",",
            ""
        )
    )

    return float(
        monto_texto
    )


# ============================================================
# DATOS GENERALES DEL ESTADO
# ============================================================

def extraer_datos_estado(
    ruta_pdf,
    password=None
):

    texto = extraer_texto_pdf(
        ruta_pdf,
        password=password
    )

    cuenta = detectar_cuenta_estado(
        texto
    )

    fecha_corte_texto = (
        extraer_fecha_corte(
            texto
        )
    )

    fecha_limite_texto = (
        extraer_fecha_limite(
            texto
        )
    )

    pago_no_intereses = (
        extraer_pago_no_intereses(
            texto
        )
    )

    fecha_corte = None

    periodo = None

    if fecha_corte_texto:

        fecha_corte = (
            convertir_fecha_estado(
                fecha_corte_texto
            )
        )

        periodo = (
            f"{NOMBRES_MESES_ESTADO[fecha_corte['mes']]} "
            f"{fecha_corte['anio']}"
        )

    fecha_limite = None

    if fecha_limite_texto:

        fecha_limite = (
            convertir_fecha_estado(
                fecha_limite_texto
            )
        )

    datos = {
        "cuenta": cuenta,

        "periodo": periodo,

        "fecha_corte": (
            None
            if fecha_corte is None
            else (
                f"{fecha_corte['dia']}/"
                f"{fecha_corte['mes']}/"
                f"{fecha_corte['anio']}"
            )
        ),

        "fecha_limite_pago": (
            None
            if fecha_limite is None
            else (
                f"{fecha_limite['dia']}/"
                f"{fecha_limite['mes']}/"
                f"{fecha_limite['anio']}"
            )
        ),

        "pago_para_no_generar_intereses": (
            pago_no_intereses
        ),
    }

    return datos


# ============================================================
# MOVIMIENTOS REGULARES INVEX
# ============================================================

def extraer_movimientos_regulares_invex(
    texto
):

    # Los PDF suelen romper líneas donde les
    # da la gana, porque aparentemente una
    # estructura predecible era demasiado pedir.

    texto_limpio = re.sub(
        r"\s+",
        " ",
        texto
    )

    patron_fecha = (
        r"\d{1,2}-"
        r"[A-Za-zÁÉÍÓÚáéíóú]+-"
        r"\d{4}"
    )

    patron_movimiento = re.compile(
        (
            rf"(?P<fecha_operacion>{patron_fecha})"
            rf"\s+"
            rf"(?P<fecha_cargo>{patron_fecha})"
            rf"\s+"
            rf"(?P<descripcion>.*?)"
            rf"\s+"
            rf"(?P<signo>[+-])"
            rf"\s*\$"
            rf"\s*"
            rf"(?P<monto>[\d,]+\.\d{{2}})"
        ),
        re.IGNORECASE
    )

    movimientos = []

    claves_vistas = set()

    for match in patron_movimiento.finditer(
        texto_limpio
    ):

        fecha_operacion = (
            match.group(
                "fecha_operacion"
            )
        )

        fecha_cargo = (
            match.group(
                "fecha_cargo"
            )
        )

        descripcion = re.sub(
            r"\s+",
            " ",
            match.group(
                "descripcion"
            )
        ).strip()

        signo = match.group(
            "signo"
        )

        monto = float(
            match.group(
                "monto"
            ).replace(
                ",",
                ""
            )
        )

        if signo == "-":

            monto *= -1

        monto = round(
            monto,
            2
        )

        clave = (
            fecha_operacion,
            fecha_cargo,
            descripcion,
            monto,
        )

        # Algunas páginas pueden repetir
        # encabezados o movimientos.
        if clave in claves_vistas:

            continue

        claves_vistas.add(
            clave
        )

        movimientos.append(
            {
                "fecha_operacion": (
                    fecha_operacion
                ),

                "fecha_cargo": (
                    fecha_cargo
                ),

                "descripcion": (
                    descripcion
                ),

                "monto": monto,
            }
        )

    return movimientos


# ============================================================
# EXTRAER UN MONTO MEDIANTE PATRÓN
# ============================================================

def extraer_monto_por_patron(
    texto,
    patron
):

    texto_limpio = re.sub(
        r"\s+",
        " ",
        texto
    )

    match = re.search(
        patron,
        texto_limpio,
        re.IGNORECASE
    )

    if match is None:

        return None

    monto = (
        match.group(1)
        .replace(
            ",",
            ""
        )
    )

    return float(
        monto
    )


# ============================================================
# RESUMEN DE CARGOS Y ABONOS
# ============================================================

def extraer_resumen_cargos_abonos(
    texto
):

    texto_limpio = re.sub(
        r"\s+",
        " ",
        texto
    )

    adeudo_anterior = extraer_monto_por_patron(
        texto_limpio,
        (
            r"Adeudo del periodo anterior"
            r"\s*(?:=\s*)?\$"
            r"([\d,]+\.\d{2})"
        )
    )

    cargos_regulares = extraer_monto_por_patron(
        texto_limpio,
        (
            r"Cargos regulares "
            r"\(no a meses\)"
            r"\s*\+\s*\$"
            r"([\d,]+\.\d{2})"
        )
    )

    # Compatible con:
    #
    # Cargos compras a meses (capital)7
    #
    # y
    #
    # Cargos y compras a meses (capital)7

    cargos_meses = extraer_monto_por_patron(
        texto_limpio,
        (
            r"Cargos\s+"
            r"(?:y\s+)?"
            r"(?:compras\s+)?"
            r"a meses\s+"
            r"\(capital\)"
            r"\d*"
            r"\s*\+\s*\$"
            r"([\d,]+\.\d{2})"
        )
    )

    intereses = extraer_monto_por_patron(
        texto_limpio,
        (
            r"Monto de intereses"
            r"\d*"
            r"\s*\+\s*\$"
            r"([\d,]+\.\d{2})"
        )
    )

    comisiones = extraer_monto_por_patron(
        texto_limpio,
        (
            r"Monto de comisiones"
            r"\s*\+\s*\$"
            r"([\d,]+\.\d{2})"
        )
    )

    iva = extraer_monto_por_patron(
        texto_limpio,
        (
            r"IVA de intereses "
            r"y comisiones"
            r"\s*\+\s*\$"
            r"([\d,]+\.\d{2})"
        )
    )

    pagos_abonos = extraer_monto_por_patron(
        texto_limpio,
        (
            r"Pagos y abonos"
            r"\s*-\s*\$"
            r"([\d,]+\.\d{2})"
        )
    )

    pago_no_intereses = extraer_monto_por_patron(
        texto_limpio,
        (
            r"PAGO PARA NO GENERAR\s+"
            r"INTERESES"
            r"\s*\d*"
            r"\s*=\s*\$"
            r"([\d,]+\.\d{2})"
        )
    )

    return {
        "adeudo_anterior": (
            adeudo_anterior
        ),

        "cargos_regulares": (
            cargos_regulares
        ),

        "cargos_meses": (
            cargos_meses
        ),

        "intereses": (
            intereses
        ),

        "comisiones": (
            comisiones
        ),

        "iva": iva,

        "pagos_abonos": (
            pagos_abonos
        ),

        "pago_no_intereses": (
            pago_no_intereses
        ),
    }


# ============================================================
# CLASIFICAR ABONOS INVEX
# ============================================================

def clasificar_abonos_invex(
    movimientos
):

    resultado = {
        "pagos_reales": [],
        "aclaraciones": [],
        "otros_abonos": [],
    }

    for movimiento in movimientos:

        monto = movimiento.get(
            "monto",
            0
        )

        # Solo queremos movimientos
        # negativos: pagos / abonos / créditos.

        if monto >= 0:

            continue

        descripcion = normalizar_texto(
            movimiento.get(
                "descripcion",
                ""
            )
        )

        # Internamente los dejamos positivos
        # porque ya sabemos que pertenecen
        # al grupo de abonos.

        movimiento_clasificado = {
            **movimiento,

            "monto": abs(
                monto
            ),
        }

        # ----------------------------------------------------
        # ACLARACIONES PROCEDENTES
        # ----------------------------------------------------

        if (
            "acl procedente"
            in descripcion
        ):

            resultado[
                "aclaraciones"
            ].append(
                movimiento_clasificado
            )

        # ----------------------------------------------------
        # PAGOS REALES
        # ----------------------------------------------------

        elif (
            "su pago"
            in descripcion
            or "pago por spei"
            in descripcion
        ):

            resultado[
                "pagos_reales"
            ].append(
                movimiento_clasificado
            )

        # ----------------------------------------------------
        # OTROS ABONOS
        # ----------------------------------------------------

        else:

            resultado[
                "otros_abonos"
            ].append(
                movimiento_clasificado
            )

    return resultado

# ============================================================
# CLASIFICAR ABONOS BANAMEX
# ============================================================

def clasificar_abonos_banamex(
    movimientos
):

    resultado = {
        "pagos_reales": [],
        "aclaraciones": [],
        "devoluciones": [],
        "otros_abonos": [],
    }

    for movimiento in movimientos:

        monto = movimiento.get(
            "monto",
            0
        )

        if monto >= 0:
            continue

        descripcion = normalizar_texto(
            movimiento.get(
                "descripcion",
                ""
            )
        )

        movimiento_clasificado = {
            **movimiento,
            "monto": abs(monto),
        }

        if (
            "su abono" in descripcion
            and "gracias" in descripcion
        ):

            resultado[
                "pagos_reales"
            ].append(
                movimiento_clasificado
            )

        else:

            resultado[
                "devoluciones"
            ].append(
                movimiento_clasificado
            )

    return resultado


def clasificar_abonos_bbva(
    movimientos
):

    resultado = {
        "pagos_reales": [],
        "aclaraciones": [],
        "devoluciones": [],
        "otros_abonos": [],
    }

    for movimiento in movimientos:

        monto = movimiento.get(
            "monto",
            0
        )

        if monto >= 0:
            continue

        descripcion = normalizar_texto(
            movimiento.get(
                "descripcion",
                ""
            )
        )

        movimiento_clasificado = {
            **movimiento,
            "monto": abs(monto),
        }

        if (
            "bmovil.pago tdc"
            in descripcion
            or "pago tdc"
            in descripcion
        ):

            resultado[
                "pagos_reales"
            ].append(
                movimiento_clasificado
            )

        else:

            resultado[
                "devoluciones"
            ].append(
                movimiento_clasificado
            )

    return resultado

def clasificar_abonos_estado(
    movimientos,
    cuenta
):

    if cuenta == "Invex":

        resultado = clasificar_abonos_invex(
            movimientos
        )

        resultado.setdefault(
            "devoluciones",
            []
        )

        return resultado

    if cuenta in (
        "Citibanamex Costco",
        "Citibanamex Oro",
    ):

        return clasificar_abonos_banamex(
            movimientos
        )

    if cuenta == "BBVA Platinum":

        return clasificar_abonos_bbva(
            movimientos
        )

    return {
        "pagos_reales": [],
        "aclaraciones": [],
        "devoluciones": [],
        "otros_abonos": [],
    }


# ============================================================
# SUMAR MOVIMIENTOS
# ============================================================

def sumar_movimientos(
    movimientos
):

    return round(
        sum(
            movimiento.get(
                "monto",
                0
            )

            for movimiento
            in movimientos
        ),
        2
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if len(
        sys.argv
    ) < 2:

        print(
            "Uso:"
        )

        print(
            (
                'python lector_estados.py '
                '"estados/archivo.pdf"'
            )
        )

        return

    ruta_pdf = sys.argv[
        1
    ]

    datos = extraer_datos_estado(
        ruta_pdf
    )

    print(
        json.dumps(
            datos,
            indent=4,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":

    main()