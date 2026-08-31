import re
import unicodedata

from datetime import datetime


# =============================
# MESES
# =============================

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


# =============================
# ALIAS DE SUBCATEGORÍAS
# =============================

ALIAS_SUBCATEGORIAS = {
    "uber": "Uber/Didi",
    "didi": "Uber/Didi",
    "gmm": "Seguro de GMM",
    "seguro medico": "Seguro de GMM",
    "plan de retiro": "Plan de Retiro",
}


# =============================
# ALIAS DE CUENTAS
# =============================

ALIAS_CUENTAS = {
    "bbva platinum": "BBVA Platinum",
    "bbva plantinum": "BBVA Platinum",
    "plantinum": "BBVA Platinum",
    "bbva debito": "BBVA Debito",
    "lineup": "LineUp",
    "santander": "Santander",
    "bbva": "BBVA Debito",
}


# =============================
# PALABRAS DE REGISTRO
# =============================

PALABRAS_REGISTRO = [
    "registra",
    "registrar",
    "registe",
    "regista",
    "anota",
    "agrega",
    "añade",
]


# =============================
# PALABRAS A IGNORAR
# AL DETECTAR DESCRIPCIÓN
# =============================

PALABRAS_IGNORAR_CONCEPTO = {
    "registra",
    "registrar",
    "registe",
    "regista",
    "anota",
    "agrega",
    "añade",
    "un",
    "una",
    "gasto",
    "ingreso",
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


# =============================
# NORMALIZACIÓN
# =============================

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


# =============================
# CONVERSIÓN DE MONTO
# =============================

def convertir_monto(monto):

    if isinstance(
        monto,
        (int, float)
    ):
        return float(monto)

    monto_limpio = (
        str(monto)
        .replace("$", "")
        .replace(",", "")
        .strip()
    )

    return float(
        monto_limpio
    )


# =============================
# CONVERSIÓN DE FECHA
# =============================

def convertir_fecha(fecha):

    if isinstance(
        fecha,
        datetime
    ):
        return fecha

    fecha_texto = str(
        fecha
    ).strip()

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


# =============================
# DETECTAR INTENCIÓN
# =============================

def detectar_intencion(mensaje):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # =============================
    # CONSULTAS
    # =============================

    palabras_consulta = [
        "cuanto",
        "cuantos",
        "total",
        "consulta",
        "consultar",
    ]

    for palabra in palabras_consulta:

        if palabra in mensaje_normalizado:
            return "consultar"

    # =============================
    # REGISTRO EXPLÍCITO
    # =============================

    for palabra in PALABRAS_REGISTRO:

        if normalizar_texto(
            palabra
        ) in mensaje_normalizado:

            return "registrar"

    # =============================
    # REGISTRO NATURAL DE GASTOS
    # =============================

    if "gaste" in mensaje_normalizado:

        monto = detectar_monto(
            mensaje
        )

        if monto is not None:
            return "registrar"

    # =============================
    # REGISTRO NATURAL DE INGRESOS
    # =============================

    palabras_ingreso_registro = [
        "recibi",
        "cobre",
        "depositaron",
        "abonaron",
        "ingrese",
    ]

    for palabra in palabras_ingreso_registro:

        if palabra in mensaje_normalizado:

            monto = detectar_monto(
                mensaje
            )

            if monto is not None:
                return "registrar"

    return "consultar"

# =============================
# DETECTAR TIPO DE MOVIMIENTO
# =============================

def detectar_tipo_movimiento(
    mensaje
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    palabras_ingreso = [
        "ingreso",
        "ingresos",
        "recibi",
        "recibiste",
        "cobre",
        "cobrado",
        "depositaron",
        "abonaron",
        "ingrese",
        "ingresado"
    ]

    for palabra in palabras_ingreso:

        if palabra in mensaje_normalizado:
            return "Ingreso"

    return "Gasto"


# =============================
# DETECTAR MONTO
# =============================

def detectar_monto(mensaje):

    texto = (
        normalizar_texto(
            mensaje
        )
        .replace("$", "")
        .replace(",", "")
    )

    # Quitamos expresiones
    # como 6 msi / 12 meses
    # para no confundir plazo
    # con monto.
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


# =============================
# DETECTAR PLAZOS
# =============================

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


# =============================
# DETECTAR MES
# =============================

def detectar_mes(mensaje):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    palabras = (
        mensaje_normalizado
        .split()
    )

    for palabra in palabras:

        palabra = palabra.strip(
            "¿?¡!.,"
        )

        if palabra in MESES:
            return MESES[
                palabra
            ]

    return None


# =============================
# DETECTAR AÑO
# =============================

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

            anio = int(
                palabra
            )

            # Evitamos cosas absurdas
            # tipo "Gasté 1200"
            # interpretado como año.
            if 1900 <= anio <= 2100:
                return anio

    return None


# =============================
# PERIODO RELATIVO
# =============================

def detectar_periodo_relativo(
    mensaje
):

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


# =============================
# DETECTAR SUBCATEGORÍA
# =============================

def detectar_subcategoria(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Primero buscamos alias.
    # Los alias largos van primero.
    for alias in sorted(
        ALIAS_SUBCATEGORIAS,
        key=len,
        reverse=True
    ):

        if (
            normalizar_texto(
                alias
            )
            in mensaje_normalizado
        ):

            return ALIAS_SUBCATEGORIAS[
                alias
            ]

    # Después buscamos
    # subcategorías existentes
    # en Google Sheets.
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
            normalizar_texto(
                subcategoria
            )
            in mensaje_normalizado
        ):

            return subcategoria

    return None


# =============================
# DETECTAR CUENTA
# =============================

def detectar_cuenta(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Alias largos primero.
    # Así BBVA Platinum
    # gana antes que BBVA.
    for alias in sorted(
        ALIAS_CUENTAS,
        key=len,
        reverse=True
    ):

        if (
            normalizar_texto(
                alias
            )
            in mensaje_normalizado
        ):

            return ALIAS_CUENTAS[
                alias
            ]

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

    cuentas_existentes = list(
        set(
            cuentas_existentes
        )
    )

    cuentas_existentes.sort(
        key=len,
        reverse=True
    )

    for cuenta in cuentas_existentes:

        if (
            normalizar_texto(
                cuenta
            )
            in mensaje_normalizado
        ):

            return cuenta

    return None


# =============================
# DETECTAR CONCEPTO / DESCRIPCIÓN
# =============================

def detectar_concepto(
    mensaje,
    cuenta=None,
    subcategoria=None
):

    texto = (
        normalizar_texto(
            mensaje
        )
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


# =============================
# DETECTAR STATUS
# =============================

def detectar_status(mensaje):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    if (
        "pendiente"
        in mensaje_normalizado
        or
        "pendientes"
        in mensaje_normalizado
    ):

        return "Pendiente"

    if (
        "pagado"
        in mensaje_normalizado
        or
        "pagados"
        in mensaje_normalizado
        or
        "pagada"
        in mensaje_normalizado
        or
        "pagadas"
        in mensaje_normalizado
    ):

        return "Pagado"

    return None


# =============================
# INTERPRETAR MENSAJE
# =============================

def interpretar_mensaje(
    mensaje,
    movimientos
):

    intencion = detectar_intencion(
        mensaje
    )

    tipo_movimiento = detectar_tipo_movimiento(
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

    # Valores por defecto
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

        if (
            tipo_movimiento == "Ingreso"
            and not concepto
            and subcategoria is not None
        ):
            concepto = subcategoria

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

            mes = periodo_relativo[
                "mes"
            ]

            anio = periodo_relativo[
                "anio"
            ]

        elif (
            mes is not None
            and anio is None
        ):

            anio = datetime.now().year

    return {
        "intencion": intencion,
        "tipo_movimiento": tipo_movimiento,
        "mes": mes,
        "anio": anio,
        "subcategoria": subcategoria,
        "cuenta": cuenta,
        "monto": monto,
        "concepto": concepto,
        "plazos": plazos,
        "status": status,
    }


# =============================
# CALCULAR TOTAL
# =============================

def calcular_total(
    movimientos,
    mes=None,
    anio=None,
    subcategoria=None,
    cuenta=None,
    status=None,
    tipo_movimiento="Gasto"
):

    total = 0.0

    for movimiento in movimientos:

        valor_tipo_movimiento = normalizar_texto(
            movimiento.get(
                "Tipo de Movimiento",
                ""
            )
        )

        if (
            valor_tipo_movimiento
            != normalizar_texto(
                tipo_movimiento
            )
        ):
            continue

        # =========================
        # FILTRO FECHA
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