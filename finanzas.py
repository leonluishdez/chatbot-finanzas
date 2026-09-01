import calendar
import re
import unicodedata

from datetime import datetime


# ============================================================
# MESES
# ============================================================

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


NOMBRES_MESES = {
    numero: nombre.capitalize()
    for nombre, numero in MESES.items()
}


# ============================================================
# CONFIGURACIÓN DE TARJETAS
# ============================================================

CONFIGURACION_TARJETAS = {

    "BBVA Platinum": {
        "dia_corte": 12,
        "dia_pago": 3,
    },

    "Citibanamex Oro": {
        "dia_corte": 9,
        "dia_pago": 29,
    },

    "Citibanamex Costco": {
        "dia_corte": 8,
        "dia_pago": 28,
    },

    "Invex": {
        "dia_corte": 13,
        "dia_pago": 4,
    },
}


# ============================================================
# ALIAS
# ============================================================

ALIAS_SUBCATEGORIAS = {

    "uber": "Uber/Didi",

    "didi": "Uber/Didi",

    "gmm": "Seguro de GMM",

    "seguro medico": "Seguro de GMM",

    "plan de retiro": "Plan de Retiro",

    "comision": "Comisiones",

    "comisiones": "Comisiones",

    "sueldo": "Sueldo",

    "bono": "Bonos",

    "bonos": "Bonos",

    "freelance": "Freelance",
}


ALIAS_CUENTAS = {

    # BBVA PLATINUM
    "bbva platinum": "BBVA Platinum",

    "bbva plantinum": "BBVA Platinum",

    "plantinum": "BBVA Platinum",

    "platinum": "BBVA Platinum",


    # BBVA DÉBITO
    "bbva debito": "BBVA Debito",


    # CITIBANAMEX ORO
    "citibanamex oro": "Citibanamex Oro",

    "banamex oro": "Citibanamex Oro",


    # CITIBANAMEX COSTCO
    "citibanamex costco": "Citibanamex Costco",

    "banamex costco": "Citibanamex Costco",

    "costco": "Citibanamex Costco",


    # INVEX
    "invex": "Invex",


    # IMPORTANTE:
    # Si simplemente dices "BBVA",
    # para gastos y estados de cuenta
    # interpretamos BBVA Platinum.
    #
    # bot.py se encarga de forzar
    # los ingresos a BBVA Debito.
    "bbva": "BBVA Platinum",
}


# ============================================================
# PALABRAS DE REGISTRO
# ============================================================

PALABRAS_REGISTRO = [

    "registra",

    "registrar",

    "registe",

    "regista",

    "anota",

    "agrega",

    "añade",
]


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

    "ingresos",

    "de",

    "con",

    "en",

    "por",

    "a",

    "pesos",

    "peso",

    "meses",

    "msi",

    "recibi",

    "cobre",

    "depositaron",

    "abonaron",

    "ingrese",
}


# ============================================================
# TEXTO
# ============================================================

def normalizar_texto(
    texto
):

    texto = str(
        texto
    ).lower().strip()

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
# MONTOS
# ============================================================

def convertir_monto(
    monto
):

    if isinstance(
        monto,
        (int, float)
    ):

        return float(
            monto
        )

    monto_limpio = (
        str(monto)
        .replace("$", "")
        .replace(",", "")
        .strip()
    )

    return float(
        monto_limpio
    )


def detectar_monto(
    mensaje
):

    texto = (
        normalizar_texto(
            mensaje
        )
        .replace("$", "")
        .replace(",", "")
    )

    # Quitamos primero expresiones
    # como:
    #
    # 6 meses
    # 12 MSI
    #
    # para que no confundamos
    # el plazo con el monto.

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


# ============================================================
# MONTO DEL ESTADO DE CUENTA
# ============================================================

def detectar_monto_estado_cuenta(
    mensaje
):

    texto = (
        normalizar_texto(
            mensaje
        )
        .replace("$", "")
        .replace(",", "")
    )

    # Ejemplo:
    #
    # Registra estado de BBVA
    # de septiembre por 8450

    match = re.search(
        r"\bpor\s+(\d+(?:\.\d+)?)\b",
        texto
    )

    if match is None:

        return None

    return float(
        match.group(1)
    )


# ============================================================
# FECHAS
# ============================================================

def convertir_fecha(
    fecha
):

    if isinstance(
        fecha,
        datetime
    ):

        return fecha

    fecha_texto = str(
        fecha
    ).strip()

    formatos = (

        "%d/%m/%y",

        "%d/%m/%Y",
    )

    for formato in formatos:

        try:

            return datetime.strptime(
                fecha_texto,
                formato
            )

        except ValueError:

            continue

    raise ValueError(
        "Formato de fecha no reconocido: "
        f"{fecha_texto}"
    )


# ============================================================
# FECHA DE COMPRA DEL MOVIMIENTO
# ============================================================

def obtener_fecha_compra_movimiento(
    movimiento
):

    fecha_compra = str(
        movimiento.get(
            "Fecha de Compra",
            ""
        )
    ).strip()

    if fecha_compra:

        return convertir_fecha(
            fecha_compra
        )

    # Compatibilidad histórica:
    #
    # Los movimientos antiguos no
    # tienen Fecha de Compra.
    #
    # En esos casos usamos
    # Fecha de Pago como referencia.

    return convertir_fecha(
        movimiento.get(
            "Fecha de Pago",
            ""
        )
    )


# ============================================================
# SUMAR MESES
# ============================================================

def sumar_meses(
    fecha,
    meses
):

    nuevo_mes = (
        fecha.month
        - 1
        + meses
    )

    nuevo_anio = (
        fecha.year
        + nuevo_mes // 12
    )

    nuevo_mes = (
        nuevo_mes % 12
        + 1
    )

    ultimo_dia = calendar.monthrange(
        nuevo_anio,
        nuevo_mes
    )[1]

    nuevo_dia = min(
        fecha.day,
        ultimo_dia
    )

    return fecha.replace(
        year=nuevo_anio,
        month=nuevo_mes,
        day=nuevo_dia
    )


# ============================================================
# CREAR FECHA VÁLIDA
# ============================================================

def crear_fecha_valida(
    anio,
    mes,
    dia
):

    ultimo_dia = calendar.monthrange(
        anio,
        mes
    )[1]

    dia_valido = min(
        dia,
        ultimo_dia
    )

    return datetime(
        anio,
        mes,
        dia_valido
    )


# ============================================================
# FECHA DE CORTE
# ============================================================

def calcular_fecha_corte(
    fecha_compra,
    cuenta
):

    configuracion = (
        CONFIGURACION_TARJETAS.get(
            cuenta
        )
    )

    if not configuracion:

        return None

    dia_corte = configuracion.get(
        "dia_corte"
    )

    if dia_corte is None:

        return None

    # Si compramos antes
    # o el mismo día del corte,
    # entra en ese corte.

    if fecha_compra.day <= dia_corte:

        return crear_fecha_valida(
            fecha_compra.year,
            fecha_compra.month,
            dia_corte
        )

    # Si compramos después,
    # entra al corte del mes siguiente.

    siguiente_mes = sumar_meses(
        fecha_compra.replace(
            day=1
        ),
        1
    )

    return crear_fecha_valida(
        siguiente_mes.year,
        siguiente_mes.month,
        dia_corte
    )


# ============================================================
# PRIMERA FECHA DE PAGO
# ============================================================

def calcular_primera_fecha_pago(
    fecha_compra,
    cuenta
):

    configuracion = (
        CONFIGURACION_TARJETAS.get(
            cuenta
        )
    )

    if not configuracion:

        return None

    dia_pago = configuracion.get(
        "dia_pago"
    )

    fecha_corte = calcular_fecha_corte(
        fecha_compra,
        cuenta
    )

    if (
        dia_pago is None
        or fecha_corte is None
    ):

        return None

    posible_pago = crear_fecha_valida(
        fecha_corte.year,
        fecha_corte.month,
        dia_pago
    )

    # Ejemplo:
    #
    # corte 9
    # pago 29
    #
    # El pago cae dentro del
    # mismo mes.

    if posible_pago > fecha_corte:

        return posible_pago

    # Ejemplo:
    #
    # corte 12
    # pago 3
    #
    # El pago cae en el
    # siguiente mes.

    siguiente_mes = sumar_meses(
        fecha_corte.replace(
            day=1
        ),
        1
    )

    return crear_fecha_valida(
        siguiente_mes.year,
        siguiente_mes.month,
        dia_pago
    )


# ============================================================
# FECHAS DE UN ESTADO DE CUENTA
# ============================================================

def calcular_fechas_estado_cuenta(
    cuenta,
    mes,
    anio
):

    configuracion = (
        CONFIGURACION_TARJETAS.get(
            cuenta
        )
    )

    if not configuracion:

        raise ValueError(
            f"No existe configuración para {cuenta}."
        )

    dia_corte = configuracion.get(
        "dia_corte"
    )

    dia_pago = configuracion.get(
        "dia_pago"
    )

    if (
        dia_corte is None
        or dia_pago is None
    ):

        raise ValueError(
            f"La configuración de {cuenta} "
            "está incompleta."
        )

    fecha_corte = crear_fecha_valida(
        anio,
        mes,
        dia_corte
    )

    posible_pago = crear_fecha_valida(
        anio,
        mes,
        dia_pago
    )

    if posible_pago > fecha_corte:

        fecha_pago = posible_pago

    else:

        siguiente_mes = sumar_meses(
            fecha_corte.replace(
                day=1
            ),
            1
        )

        fecha_pago = crear_fecha_valida(
            siguiente_mes.year,
            siguiente_mes.month,
            dia_pago
        )

    return (
        fecha_corte,
        fecha_pago
    )


# ============================================================
# INTENCIÓN
# ============================================================

def detectar_intencion(
    mensaje
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # -------------------------
    # CONSULTAS
    # -------------------------

    palabras_consulta = [

        "cuanto",

        "cuantos",

        "total",

        "consulta",

        "consultar",

        "que tengo que pagar",

        "que debo",
    ]

    if any(
        palabra in mensaje_normalizado
        for palabra in palabras_consulta
    ):

        return "consultar"

    # -------------------------
    # REGISTRO EXPLÍCITO
    # -------------------------

    if any(
        normalizar_texto(
            palabra
        ) in mensaje_normalizado

        for palabra in PALABRAS_REGISTRO
    ):

        return "registrar"

    # -------------------------
    # REGISTRO NATURAL
    # DE GASTOS
    # -------------------------

    if (
        "gaste" in mensaje_normalizado
        and detectar_monto(
            mensaje
        ) is not None
    ):

        return "registrar"

    # -------------------------
    # REGISTRO NATURAL
    # DE INGRESOS
    # -------------------------

    palabras_ingreso_registro = [

        "recibi",

        "cobre",

        "depositaron",

        "abonaron",

        "ingrese",
    ]

    if any(
        palabra in mensaje_normalizado
        for palabra in palabras_ingreso_registro
    ):

        if detectar_monto(
            mensaje
        ) is not None:

            return "registrar"

    return "consultar"


# ============================================================
# TIPO DE MOVIMIENTO
# ============================================================

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

        "ingresado",
    ]

    if any(
        palabra in mensaje_normalizado
        for palabra in palabras_ingreso
    ):

        return "Ingreso"

    return "Gasto"


# ============================================================
# PLAZOS
# ============================================================

def detectar_plazos(
    mensaje
):

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


# ============================================================
# DETECTAR VARIOS MESES
# ============================================================

def detectar_meses(
    mensaje
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    palabras = re.findall(
        r"\b[a-z]+\b",
        mensaje_normalizado
    )

    meses_encontrados = []

    for palabra in palabras:

        if palabra in MESES:

            numero_mes = MESES[
                palabra
            ]

            if (
                numero_mes
                not in meses_encontrados
            ):

                meses_encontrados.append(
                    numero_mes
                )

    return meses_encontrados


# ============================================================
# DETECTAR UN MES
# ============================================================

def detectar_mes(
    mensaje
):

    meses = detectar_meses(
        mensaje
    )

    if meses:

        return meses[
            0
        ]

    return None


# ============================================================
# PRÓXIMOS N MESES
# ============================================================

def detectar_proximos_meses(
    mensaje
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    match = re.search(
        r"\bproximos?\s+(\d+)\s+meses\b",
        mensaje_normalizado
    )

    if match is None:

        return []

    cantidad = int(
        match.group(1)
    )

    if cantidad < 1:

        return []

    hoy = datetime.now()

    periodos = []

    for desplazamiento in range(
        1,
        cantidad + 1
    ):

        fecha = sumar_meses(
            hoy.replace(
                day=1
            ),
            desplazamiento
        )

        periodos.append(
            {
                "mes": fecha.month,
                "anio": fecha.year,
            }
        )

    return periodos


# ============================================================
# AÑO
# ============================================================

def detectar_anio(
    mensaje
):

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

            if (
                1900
                <= anio
                <= 2100
            ):

                return anio

    return None


# ============================================================
# PERIODO RELATIVO
# ============================================================

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


# ============================================================
# SUBCATEGORÍA
# ============================================================

def detectar_subcategoria(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Primero buscamos alias.

    for alias in sorted(
        ALIAS_SUBCATEGORIAS,
        key=len,
        reverse=True
    ):

        if normalizar_texto(
            alias
        ) in mensaje_normalizado:

            return ALIAS_SUBCATEGORIAS[
                alias
            ]

    # Después usamos las
    # subcategorías existentes
    # en Google Sheets.

    for movimiento in movimientos:

        subcategoria = str(
            movimiento.get(
                "Subcategoria",
                ""
            )
        ).strip()

        if (
            subcategoria
            and normalizar_texto(
                subcategoria
            ) in mensaje_normalizado
        ):

            return subcategoria

    return None


# ============================================================
# CUENTA
# ============================================================

def detectar_cuenta(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Alias conocidos.
    #
    # Revisamos primero los
    # más largos.

    for alias in sorted(
        ALIAS_CUENTAS,
        key=len,
        reverse=True
    ):

        if normalizar_texto(
            alias
        ) in mensaje_normalizado:

            return ALIAS_CUENTAS[
                alias
            ]

    # Después buscamos cuentas
    # históricas en Sheets.

    cuentas = {

        str(
            movimiento.get(
                "Cuenta",
                ""
            )
        ).strip()

        for movimiento in movimientos

        if str(
            movimiento.get(
                "Cuenta",
                ""
            )
        ).strip()
    }

    for cuenta in sorted(
        cuentas,
        key=len,
        reverse=True
    ):

        if normalizar_texto(
            cuenta
        ) in mensaje_normalizado:

            return cuenta

    return None


# ============================================================
# CONCEPTO
# ============================================================

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

    palabras_cuenta = (

        set(
            normalizar_texto(
                cuenta
            ).split()
        )

        if cuenta

        else set()
    )

    palabras_subcategoria = (

        set(
            normalizar_texto(
                subcategoria
            ).split()
        )

        if subcategoria

        else set()
    )

    concepto_palabras = []

    for palabra in palabras:

        palabra = palabra.strip(
            "¿?¡!.,"
        )

        if (
            palabra
            in PALABRAS_IGNORAR_CONCEPTO
        ):

            continue

        # Quitamos montos,
        # plazos y años.

        try:

            float(
                palabra
            )

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


# ============================================================
# STATUS
# ============================================================

def detectar_status(
    mensaje
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    palabras_pendiente = [

        "pendiente",

        "pendientes",

        "debo",

        "deuda",

        "por pagar",

        "pagar",

        "comprometido",

        "comprometidos",

        "comprometida",

        "comprometidas",
    ]

    if any(
        palabra in mensaje_normalizado
        for palabra in palabras_pendiente
    ):

        return "Pendiente"

    palabras_pagado = [

        "pagado",

        "pagados",

        "pagada",

        "pagadas",
    ]

    if any(
        palabra in mensaje_normalizado
        for palabra in palabras_pagado
    ):

        return "Pagado"

    return None


# ============================================================
# TIPO DE PAGO
# ============================================================

def detectar_tipo_pago(
    mensaje
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # "Próximos 3 meses"
    # habla de un periodo.
    #
    # NO significa MSI.

    if re.search(
        r"\bproximos?\s+\d+\s+meses\b",
        mensaje_normalizado
    ):

        return None

    palabras_meses = [

        "compras a meses",

        "mensualidad",

        "mensualidades",

        "msi",
    ]

    if any(
        palabra in mensaje_normalizado
        for palabra in palabras_meses
    ):

        return "Meses"

    # Registro natural:
    #
    # "a 6 meses"

    if re.search(
        r"\b\d+\s+meses\b",
        mensaje_normalizado
    ):

        return "Meses"

    if "contado" in mensaje_normalizado:

        return "Contado"

    return None


# ============================================================
# PARSER DE ESTADOS DE CUENTA
# ============================================================

def interpretar_estado_cuenta(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Solo entra aquí si
    # realmente dice "estado".

    if "estado" not in mensaje_normalizado:

        return None

    es_registro = any(

        normalizar_texto(
            palabra
        ) in mensaje_normalizado

        for palabra in PALABRAS_REGISTRO
    )

    if not es_registro:

        return None

    cuenta = detectar_cuenta(
        mensaje,
        movimientos
    )

    mes = detectar_mes(
        mensaje
    )

    anio = detectar_anio(
        mensaje
    )

    monto = detectar_monto_estado_cuenta(
        mensaje
    )

    if (
        mes is not None
        and anio is None
    ):

        anio = datetime.now().year

    return {
        "cuenta": cuenta,
        "mes": mes,
        "anio": anio,
        "monto": monto,
    }


# ============================================================
# PARSER GENERAL
# ============================================================

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

    tipo_pago = detectar_tipo_pago(
        mensaje
    )

    # Valores por defecto.

    mes = None

    meses = []

    periodos = []

    anio = None

    monto = None

    concepto = ""

    plazos = 1


    # ========================================================
    # REGISTRAR
    # ========================================================

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

        # Si estamos registrando
        # un ingreso y ya detectamos
        # "Comisiones", "Sueldo", etc.,
        # usamos esa categoría como
        # descripción si no encontramos
        # otro concepto.

        if (
            tipo_movimiento == "Ingreso"
            and not concepto
            and subcategoria is not None
        ):

            concepto = subcategoria


    # ========================================================
    # CONSULTAR
    # ========================================================

    else:

        # -------------------------
        # PRÓXIMOS N MESES
        # -------------------------

        periodos = detectar_proximos_meses(
            mensaje
        )

        # -------------------------
        # PERIODO RELATIVO
        # -------------------------

        periodo_relativo = (
            detectar_periodo_relativo(
                mensaje
            )
        )

        # -------------------------
        # MESES ESCRITOS
        # -------------------------

        meses = detectar_meses(
            mensaje
        )

        anio = detectar_anio(
            mensaje
        )

        # Prioridad 1:
        #
        # "próximos 3 meses"

        if periodos:

            mes = None

            meses = []

            anio = None


        # Prioridad 2:
        #
        # "este mes"

        elif periodo_relativo is not None:

            mes = periodo_relativo[
                "mes"
            ]

            meses = [
                mes
            ]

            anio = periodo_relativo[
                "anio"
            ]


        # -------------------------
        # UN MES EXPLÍCITO
        # -------------------------

        elif len(
            meses
        ) == 1:

            mes = meses[
                0
            ]

            if anio is None:

                anio = datetime.now().year


        # -------------------------
        # VARIOS MESES
        # -------------------------

        elif len(
            meses
        ) > 1:

            mes = None

            if anio is None:

                anio = datetime.now().year


    return {

        "intencion": intencion,

        "tipo_movimiento": tipo_movimiento,

        "mes": mes,

        "meses": meses,

        "periodos": periodos,

        "anio": anio,

        "subcategoria": subcategoria,

        "cuenta": cuenta,

        "monto": monto,

        "concepto": concepto,

        "plazos": plazos,

        "status": status,

        "tipo_pago": tipo_pago,
    }


# ============================================================
# FILTRAR MOVIMIENTOS
# ============================================================

def obtener_movimientos_filtrados(
    movimientos,
    mes=None,
    anio=None,
    subcategoria=None,
    cuenta=None,
    status=None,
    tipo_pago=None,
    tipo_movimiento="Gasto"
):

    resultados = []

    for movimiento in movimientos:


        # -------------------------
        # TIPO DE MOVIMIENTO
        # -------------------------

        valor_tipo = normalizar_texto(
            movimiento.get(
                "Tipo de Movimiento",
                ""
            )
        )

        if (
            valor_tipo
            != normalizar_texto(
                tipo_movimiento
            )
        ):

            continue


        # -------------------------
        # FECHA DE PAGO
        # -------------------------

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


        # -------------------------
        # SUBCATEGORÍA
        # -------------------------

        if subcategoria is not None:

            valor = normalizar_texto(
                movimiento.get(
                    "Subcategoria",
                    ""
                )
            )

            if (
                valor
                != normalizar_texto(
                    subcategoria
                )
            ):

                continue


        # -------------------------
        # CUENTA
        # -------------------------

        if cuenta is not None:

            valor = normalizar_texto(
                movimiento.get(
                    "Cuenta",
                    ""
                )
            )

            if (
                valor
                != normalizar_texto(
                    cuenta
                )
            ):

                continue


        # -------------------------
        # STATUS
        # -------------------------

        if status is not None:

            valor = normalizar_texto(
                movimiento.get(
                    "Status",
                    ""
                )
            )

            if (
                valor
                != normalizar_texto(
                    status
                )
            ):

                continue


        # -------------------------
        # TIPO DE PAGO
        # -------------------------

        if tipo_pago is not None:

            valor = normalizar_texto(
                movimiento.get(
                    "Tipo de Pago",
                    ""
                )
            )

            if (
                valor
                != normalizar_texto(
                    tipo_pago
                )
            ):

                continue


        resultados.append(
            movimiento
        )


    return resultados


# ============================================================
# CALCULAR TOTAL
# ============================================================

def calcular_total(
    movimientos,
    mes=None,
    anio=None,
    subcategoria=None,
    cuenta=None,
    status=None,
    tipo_pago=None,
    tipo_movimiento="Gasto"
):

    filtrados = obtener_movimientos_filtrados(

        movimientos,

        mes=mes,

        anio=anio,

        subcategoria=subcategoria,

        cuenta=cuenta,

        status=status,

        tipo_pago=tipo_pago,

        tipo_movimiento=tipo_movimiento
    )


    total = 0.0


    for movimiento in filtrados:

        try:

            total += convertir_monto(
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


    return round(
        total,
        2
    )


# ============================================================
# TOTAL POR FECHA EXACTA DE PAGO
# ============================================================

def calcular_total_fecha_pago(
    movimientos,
    cuenta,
    fecha_pago
):

    # Esta función se usa para
    # la conciliación bancaria.
    #
    # Ejemplo:
    #
    # Estado BBVA septiembre
    # Fecha límite: 03/10/2026
    #
    # Buscamos todos los movimientos
    # de BBVA cuya Fecha de Pago sea
    # exactamente 03/10/2026.

    if isinstance(
        fecha_pago,
        datetime
    ):

        fecha_objetivo = fecha_pago

    else:

        fecha_objetivo = convertir_fecha(
            fecha_pago
        )


    total = 0.0


    for movimiento in movimientos:


        # -------------------------
        # SOLO GASTOS
        # -------------------------

        tipo_movimiento = normalizar_texto(
            movimiento.get(
                "Tipo de Movimiento",
                ""
            )
        )

        if tipo_movimiento != "gasto":

            continue


        # -------------------------
        # MISMA CUENTA
        # -------------------------

        cuenta_movimiento = normalizar_texto(
            movimiento.get(
                "Cuenta",
                ""
            )
        )

        if (
            cuenta_movimiento
            != normalizar_texto(
                cuenta
            )
        ):

            continue


        # -------------------------
        # MISMA FECHA DE PAGO
        # -------------------------

        try:

            fecha_movimiento = convertir_fecha(
                movimiento.get(
                    "Fecha de Pago",
                    ""
                )
            )

        except ValueError:

            continue


        if (
            fecha_movimiento.date()
            != fecha_objetivo.date()
        ):

            continue


        # -------------------------
        # SUMAR MONTO
        # -------------------------

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


    return round(
        total,
        2
    )

def obtener_movimientos_fecha_pago(
    movimientos,
    cuenta,
    fecha_pago
):

    if isinstance(
        fecha_pago,
        datetime
    ):

        fecha_objetivo = fecha_pago

    else:

        fecha_objetivo = convertir_fecha(
            fecha_pago
        )

    resultados = []

    for movimiento in movimientos:

        tipo_movimiento = normalizar_texto(
            movimiento.get(
                "Tipo de Movimiento",
                ""
            )
        )

        if tipo_movimiento != "gasto":
            continue

        cuenta_movimiento = normalizar_texto(
            movimiento.get(
                "Cuenta",
                ""
            )
        )

        if cuenta_movimiento != normalizar_texto(
            cuenta
        ):

            continue

        try:

            fecha_movimiento = convertir_fecha(
                movimiento.get(
                    "Fecha de Pago",
                    ""
                )
            )

        except ValueError:

            continue

        if (
            fecha_movimiento.date()
            != fecha_objetivo.date()
        ):

            continue

        resultados.append(
            movimiento
        )

    return resultados


def interpretar_consulta_estado_cuenta(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    if "estado" not in mensaje_normalizado:

        return None

    es_registro = any(
        normalizar_texto(
            palabra
        ) in mensaje_normalizado

        for palabra in PALABRAS_REGISTRO
    )

    if es_registro:

        return None

    cuenta = detectar_cuenta(
        mensaje,
        movimientos
    )

    mes = detectar_mes(
        mensaje
    )

    anio = detectar_anio(
        mensaje
    )

    if (
        mes is not None
        and anio is None
    ):

        anio = datetime.now().year

    return {
        "cuenta": cuenta,
        "mes": mes,
        "anio": anio,
    }


def buscar_estado_cuenta(
    estados_cuenta,
    cuenta,
    mes,
    anio
):

    periodo_buscado = normalizar_texto(
        (
            f"{NOMBRES_MESES[mes]} "
            f"{anio}"
        )
    )

    # Lo recorremos al revés.
    # Si accidentalmente registramos
    # dos veces el mismo estado,
    # usamos el más reciente.
    for estado in reversed(
        estados_cuenta
    ):

        cuenta_estado = normalizar_texto(
            estado.get(
                "Cuenta",
                ""
            )
        )

        periodo_estado = normalizar_texto(
            estado.get(
                "Periodo",
                ""
            )
        )

        if (
            cuenta_estado
            == normalizar_texto(
                cuenta
            )
            and periodo_estado
            == periodo_buscado
        ):

            return estado

    return None


# ============================================================
# DIVIDIR MONTO EN PLAZOS
# ============================================================

def dividir_monto_en_plazos(
    monto_total,
    plazos
):

    if plazos <= 1:

        return [
            round(
                monto_total,
                2
            )
        ]

    monto_base = round(
        monto_total / plazos,
        2
    )

    montos = [

        monto_base

        for _ in range(
            plazos
        )
    ]

    diferencia = round(
        monto_total
        - sum(
            montos
        ),
        2
    )

    montos[
        -1
    ] = round(
        montos[
            -1
        ]
        + diferencia,
        2
    )

    return montos


# ============================================================
# GENERAR FECHAS DE PLAZOS
# ============================================================

def generar_fechas_plazos(
    fecha_inicial,
    plazos
):

    return [

        sumar_meses(
            fecha_inicial,
            numero
        )

        for numero in range(
            plazos
        )
    ]


# ============================================================
# GENERAR CUOTAS MSI
# ============================================================

def generar_cuotas(
    monto_total,
    plazos,
    fecha_compra,
    descripcion,
    cuenta
):

    montos = dividir_monto_en_plazos(
        monto_total,
        plazos
    )

    primera_fecha_pago = (
        calcular_primera_fecha_pago(
            fecha_compra,
            cuenta
        )
    )

    if primera_fecha_pago is None:

        raise ValueError(
            "No existe configuración completa "
            "de corte y pago para la cuenta: "
            f"{cuenta}"
        )


    cuotas = []


    for indice in range(
        plazos
    ):

        numero = indice + 1


        fecha_pago = sumar_meses(
            primera_fecha_pago,
            indice
        )


        cuota = {

            "numero": numero,

            "plazos": plazos,

            "monto": montos[
                indice
            ],

            "fecha": fecha_pago,

            "descripcion": (
                f"{descripcion} "
                f"{numero} de {plazos}"
            ),
        }


        cuotas.append(
            cuota
        )


    return cuotas