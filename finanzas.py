import re
import unicodedata
from datetime import datetime


MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


ALIAS_SUBCATEGORIAS = {
    "uber": "Uber/Didi",
    "didi": "Uber/Didi",
    "gmm": "Seguro de GMM",
    "seguro medico": "Seguro de GMM",
    "plan de retiro": "Plan de Retiro",
}


ALIAS_CUENTAS = {
    "bbva platinum": "BBVA Platinum",
    "bbva plantinum": "BBVA Platinum",
    "plantinum": "BBVA Platinum",
    "bbva debito": "BBVA Debito",
    "lineup": "LineUp",
    "santander": "Santander",
    "bbva": "BBVA Debito",
}


PALABRAS_REGISTRO = [
    "registra",
    "registrar",
    "regista",
    "anota",
    "agrega",
    "añade",
]


PALABRAS_IGNORAR_CONCEPTO = {
    "registra",
    "registrar",
    "regista",
    "anota",
    "agrega",
    "añade",
    "un",
    "una",
    "gasto",
    "de",
    "con",
    "en",
    "por",
    "pesos",
    "peso",
    "a",
    "meses",
    "msi",
}


def normalizar_texto(texto):

    texto = str(texto).lower().strip()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    return texto


def convertir_monto(monto):

    if isinstance(monto, (int, float)):
        return float(monto)

    monto_limpio = (
        str(monto)
        .replace("$", "")
        .replace(",", "")
        .strip()
    )

    return float(monto_limpio)


def convertir_fecha(fecha):

    if isinstance(fecha, datetime):
        return fecha

    fecha_texto = str(fecha).strip()

    formatos = [
        "%d/%m/%y",
        "%d/%m/%Y",
    ]

    for formato in formatos:

        try:

            return datetime.strptime(
                fecha_texto,
                formato
            )

        except ValueError:

            continue

    raise ValueError(
        f"Formato de fecha no reconocido: {fecha_texto}"
    )


def detectar_intencion(mensaje):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Frases claramente de consulta
    palabras_consulta = [
        "cuanto",
        "cuantos",
        "total",
        "consulta",
        "consultar"
    ]

    for palabra in palabras_consulta:

        if palabra in mensaje_normalizado:
            return "consultar"

    # Verbos explícitos de registro
    palabras_registro = [
        "registra",
        "registrar",
        "registe",
        "regista",
        "anota",
        "agrega",
        "añade"
    ]

    for palabra in palabras_registro:

        if palabra in mensaje_normalizado:
            return "registrar"

    # Lenguaje natural:
    # "gasté 200 en tacos"
    if "gaste" in mensaje_normalizado:

        monto = detectar_monto(
            mensaje
        )

        if monto is not None:
            return "registrar"

    return "consultar"


def detectar_monto(mensaje):

    texto = (
        normalizar_texto(mensaje)
        .replace("$", "")
        .replace(",", "")
    )

    # Quitamos primero expresiones como:
    # 6 msi / 12 meses
    # para no confundir el plazo con el monto.
    texto = re.sub(
        r"\b\d+\s*(?:meses|msi)\b",
        "",
        texto
    )

    match = re.search(
        r"\b\d+(?:\.\d+)?\b",
        texto
    )

    if match is None:
        return None

    return float(
        match.group()
    )


def detectar_plazos(mensaje):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    match = re.search(
        r"\b(\d+)\s*(?:meses|msi)\b",
        mensaje_normalizado
    )

    if match is None:
        return 1

    return int(
        match.group(1)
    )


def detectar_mes(mensaje):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    palabras = mensaje_normalizado.split()

    for palabra in palabras:

        palabra = palabra.strip(
            "¿?¡!.,"
        )

        if palabra in MESES:

            return MESES[palabra]

    return None


def detectar_anio(mensaje):

    palabras = normalizar_texto(
        mensaje
    ).split()

    for palabra in palabras:

        palabra = palabra.strip(
            "¿?¡!.,"
        )

        if (
            palabra.isdigit()
            and len(palabra) == 4
        ):

            return int(palabra)

    return None


def detectar_periodo_relativo(mensaje):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    hoy = datetime.now()

    if "este mes" in mensaje_normalizado:

        return {
            "mes": hoy.month,
            "anio": hoy.year,
        }

    return None


def detectar_subcategoria(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Primero buscamos alias.
    # Los más largos se revisan primero.
    for alias in sorted(
        ALIAS_SUBCATEGORIAS,
        key=len,
        reverse=True
    ):

        if normalizar_texto(alias) in mensaje_normalizado:

            return ALIAS_SUBCATEGORIAS[
                alias
            ]

    # Después usamos las subcategorías
    # que ya existen en Google Sheets.
    for movimiento in movimientos:

        subcategoria = str(
            movimiento.get(
                "Subcategoria",
                ""
            )
        ).strip()

        if not subcategoria:
            continue

        if (
            normalizar_texto(subcategoria)
            in mensaje_normalizado
        ):

            return subcategoria

    return None


def detectar_cuenta(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Importante:
    # buscamos primero los alias largos.
    # Así "bbva platinum" gana antes que "bbva".
    for alias in sorted(
        ALIAS_CUENTAS,
        key=len,
        reverse=True
    ):

        if normalizar_texto(alias) in mensaje_normalizado:

            return ALIAS_CUENTAS[
                alias
            ]

    # También buscamos directamente
    # las cuentas existentes en Sheets.
    cuentas_existentes = []

    for movimiento in movimientos:

        cuenta = str(
            movimiento.get(
                "Cuenta",
                ""
            )
        ).strip()

        if cuenta:
            cuentas_existentes.append(
                cuenta
            )

    cuentas_existentes.sort(
        key=len,
        reverse=True
    )

    for cuenta in cuentas_existentes:

        if (
            normalizar_texto(cuenta)
            in mensaje_normalizado
        ):

            return cuenta

    return None


def detectar_concepto(
    mensaje,
    cuenta=None,
    subcategoria=None
):

    texto = (
        normalizar_texto(mensaje)
        .replace("$", "")
        .replace(",", "")
    )

    palabras = texto.split()

    palabras_cuenta = set()

    if cuenta is not None:

        palabras_cuenta = set(
            normalizar_texto(
                cuenta
            ).split()
        )

    palabras_subcategoria = set()

    if subcategoria is not None:

        palabras_subcategoria = set(
            normalizar_texto(
                subcategoria
            ).split()
        )

    concepto_palabras = []

    for palabra in palabras:

        if (
            palabra
            in PALABRAS_IGNORAR_CONCEPTO
        ):
            continue

        # Quitamos números:
        # monto y plazos.
        try:
            float(palabra)
            continue

        except ValueError:
            pass

        if palabra in palabras_cuenta:
            continue

        if palabra in palabras_subcategoria:
            continue

        concepto_palabras.append(
            palabra
        )

    concepto = " ".join(
        concepto_palabras
    ).strip()

    if concepto:
        return concepto.capitalize()

    return ""

def detectar_status(mensaje):

    mensaje = normalizar_texto(
        mensaje
    )

    if (
        "pendiente" in mensaje
        or "pendientes" in mensaje
    ):
        return "Pendiente"

    if (
        "pagado" in mensaje
        or "pagados" in mensaje
        or "pagada" in mensaje
        or "pagadas" in mensaje
    ):
        return "Pagado"

    return None


def interpretar_mensaje(
    mensaje,
    movimientos
):

    intencion = detectar_intencion(
        mensaje
    )

    subcategoria = detectar_subcategoria(
        mensaje,
        movimientos
    )

    cuenta = detectar_cuenta(
        mensaje,
        movimientos
    )

    status = detectar_status(
    mensaje
    )

    # Valores por defecto.
    mes = None
    anio = None
    monto = None
    concepto = ""
    plazos = 1

    # =========================
    # REGISTRO
    # =========================

    if intencion == "registrar":

        monto = detectar_monto(
            mensaje
        )

        plazos = detectar_plazos(
            mensaje
        )

        concepto = detectar_concepto(
            mensaje,
            cuenta,
            subcategoria
        )

    # =========================
    # CONSULTA
    # =========================

    else:

        mes = detectar_mes(
            mensaje
        )

        anio = detectar_anio(
            mensaje
        )

        periodo_relativo = (
            detectar_periodo_relativo(
                mensaje
            )
        )

        if periodo_relativo is not None:

            mes = periodo_relativo["mes"]
            anio = periodo_relativo["anio"]

        # Si dice "en agosto" y no dice año,
        # asumimos el año actual.
        elif (
            mes is not None
            and anio is None
        ):

            anio = datetime.now().year

    return {
        "intencion": intencion,
        "mes": mes,
        "anio": anio,
        "subcategoria": subcategoria,
        "cuenta": cuenta,
        "monto": monto,
        "concepto": concepto,
        "plazos": plazos,
        "status": status,
    }


def calcular_total(
    movimientos,
    mes=None,
    anio=None,
    subcategoria=None,
    cuenta=None,
    status=None
):

    total = 0.0

    for movimiento in movimientos:

        tipo_movimiento = normalizar_texto(
            movimiento.get(
                "Tipo de Movimiento",
                ""
            )
        )

        if tipo_movimiento != "gasto":
            continue

        # =========================
        # FILTRO DE FECHA
        # =========================

        if (
            mes is not None
            or anio is not None
        ):

            try:

                fecha = convertir_fecha(
                    movimiento.get(
                        "Fecha de Pago",
                        ""
                    )
                )

            except ValueError:

                continue

            if (
                mes is not None
                and fecha.month != mes
            ):
                continue

            if (
                anio is not None
                and fecha.year != anio
            ):
                continue

        # =========================
        # FILTRO SUBCATEGORÍA
        # =========================

        if subcategoria is not None:

            valor_subcategoria = (
                normalizar_texto(
                    movimiento.get(
                        "Subcategoria",
                        ""
                    )
                )
            )

            if (
                valor_subcategoria
                != normalizar_texto(
                    subcategoria
                )
            ):
                continue

        # =========================
        # FILTRO CUENTA
        # =========================

        if cuenta is not None:

            valor_cuenta = normalizar_texto(
                movimiento.get(
                    "Cuenta",
                    ""
                )
            )

            if (
                valor_cuenta
                != normalizar_texto(
                    cuenta
                )
            ):
                continue
        # =========================
        # FILTRO STATUS
        # =========================

        if status is not None:

            valor_status = normalizar_texto(
                movimiento.get(
                    "Status",
                    ""
                )
            )

            if (
                valor_status
                != normalizar_texto(
                    status
                )
            ):
                continue

        # =========================
        # SUMAR MONTO
        # =========================

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

        total += monto

    return total