import calendar
import re
import unicodedata

from datetime import datetime
from decimal import (
    Decimal,
    ROUND_HALF_UP,
    ROUND_CEILING,
)


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
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


# ============================================================
# CONFIGURACIÓN DE TARJETAS
# ============================================================
#
# Estas fechas sirven para PROYECTAR compras nuevas.
#
# IMPORTANTE:
# Cuando importamos un estado PDF usamos las fechas REALES
# encontradas en el documento, no estas fechas estimadas.
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
# ALIAS DE SUBCATEGORÍAS
# ============================================================

ALIAS_SUBCATEGORIAS = {
    "uber eats": "Comida a domicilio",
    "didi food": "Comida a domicilio",
    "rappi": "Comida a domicilio",
    "comida a domicilio": "Comida a domicilio",
    "restaurantes": "Restaurantes y cafeterías",
    "cafeterias": "Restaurantes y cafeterías",
    "supermercado": "Supermercado y despensa",
    "comida": "Alimentación",
    "uber": "Transporte",
    "didi": "Transporte",
    "gmm": "Seguros",
    "seguro medico": "Seguros",
    "plan de retiro": "Ahorro y retiro",
}


# ============================================================
# ALIAS DE CUENTAS
# ============================================================

ALIAS_CUENTAS = {

    # BBVA Platinum
    "bbva platinum": "BBVA Platinum",
    "bbva plantinum": "BBVA Platinum",
    "plantinum": "BBVA Platinum",
    "platinum": "BBVA Platinum",

    # Cuando hablamos simplemente de BBVA en gastos
    "bbva": "BBVA Platinum",

    # Débito
    "bbva debito": "BBVA Debito",

    # Citibanamex Oro
    "citibanamex oro": "Citibanamex Oro",
    "banamex oro": "Citibanamex Oro",

    # Citibanamex Costco
    "citibanamex costco": "Citibanamex Costco",
    "banamex costco": "Citibanamex Costco",
    "costco": "Citibanamex Costco",

    # Invex
    "invex": "Invex",
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


# ============================================================
# PALABRAS A IGNORAR EN CONCEPTO
# ============================================================

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
# NORMALIZAR TEXTO
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

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(
            caracter
        ) != "Mn"
    )

    return texto


# ============================================================
# CONVERTIR MONTO
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

    if not monto_limpio:

        return 0.0

    return float(
        monto_limpio
    )


# ============================================================
# CONVERTIR FECHA
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

    # Compatibilidad con movimientos históricos
    # que todavía no tienen Fecha de Compra.

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

    if configuracion is None:

        return None

    dia_corte = configuracion.get(
        "dia_corte"
    )

    if dia_corte is None:

        return None

    if fecha_compra.day <= dia_corte:

        return crear_fecha_valida(
            fecha_compra.year,
            fecha_compra.month,
            dia_corte
        )

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

    if configuracion is None:

        return None

    dia_pago = configuracion.get(
        "dia_pago"
    )

    if dia_pago is None:

        return None

    fecha_corte = calcular_fecha_corte(
        fecha_compra,
        cuenta
    )

    if fecha_corte is None:

        return None

    posible_pago = crear_fecha_valida(
        fecha_corte.year,
        fecha_corte.month,
        dia_pago
    )

    # Si el día de pago está después
    # del corte, corresponde al mismo mes.

    if posible_pago > fecha_corte:

        return posible_pago

    # Si no, corresponde al siguiente mes.

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
# FECHAS DE ESTADO MANUAL
# ============================================================
#
# Se usa cuando registramos manualmente desde Telegram:
#
# "Registra estado de BBVA de septiembre por 8450"
#
# Los PDFs importados NO dependen de esta función.
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

    if configuracion is None:

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
            f"La configuración de {cuenta} está incompleta."
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
# DETECTAR INTENCIÓN
# ============================================================

def detectar_intencion(
    mensaje
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Consultas claras

    palabras_consulta = [
        "cuanto",
        "cuantos",
        "total",
        "consulta",
        "consultar",
        "que tengo que pagar",
        "que debo",
    ]

    for palabra in palabras_consulta:

        if palabra in mensaje_normalizado:

            return "consultar"

    # Registro explícito

    for palabra in PALABRAS_REGISTRO:

        if normalizar_texto(
            palabra
        ) in mensaje_normalizado:

            return "registrar"

    # Registro natural de gastos:
    # "Gasté 200 en tacos"

    if "gaste" in mensaje_normalizado:

        monto = detectar_monto(
            mensaje
        )

        if monto is not None:

            return "registrar"

    # Registro natural de ingresos

    palabras_ingreso = [
        "recibi",
        "cobre",
        "depositaron",
        "abonaron",
        "ingrese",
    ]

    for palabra in palabras_ingreso:

        if palabra in mensaje_normalizado:

            monto = detectar_monto(
                mensaje
            )

            if monto is not None:

                return "registrar"

    return "consultar"


# ============================================================
# DETECTAR TIPO DE MOVIMIENTO
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

    for palabra in palabras_ingreso:

        if palabra in mensaje_normalizado:

            return "Ingreso"

    return "Gasto"


# ============================================================
# DETECTAR MONTO
# ============================================================

def detectar_monto(
    mensaje
):

    texto = normalizar_texto(
        mensaje
    )

    texto = (
        texto
        .replace("$", "")
        .replace(",", "")
    )

    # Evitamos interpretar los plazos como monto.
    #
    # "1200 a 6 meses"
    # debe devolver 1200, no 6.

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

    texto = normalizar_texto(
        mensaje
    )

    texto = (
        texto
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
# DETECTAR PLAZOS
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
# DETECTAR MES
# ============================================================

def detectar_mes(
    mensaje
):

    meses = detectar_meses(
        mensaje
    )

    if meses:

        return meses[0]

    return None


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
# DETECTAR AÑO
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

            if 1900 <= anio <= 2100:

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
# DETECTAR SUBCATEGORÍA
# ============================================================

def detectar_subcategoria(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Primero alias

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

    # Después categorías existentes en Sheets

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


# ============================================================
# DETECTAR CUENTA
# ============================================================

def detectar_cuenta(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Las cuentas de Sheets son la fuente de verdad para consultas.
    # Primero buscamos el nombre completo y después una coincidencia
    # significativa (por ejemplo, "Caja Popular" para
    # "Caja Popular Mexicana"). Los alias sólo conservan comodidad para
    # nombres cortos de las tarjetas configuradas.

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

    coincidencias_parciales = []

    for cuenta in cuentas_existentes:

        palabras = [
            palabra
            for palabra in normalizar_texto(cuenta).split()
            if len(palabra) > 2
        ]

        for inicio in range(len(palabras)):

            for fin in range(len(palabras), inicio + 1, -1):

                fragmento = " ".join(palabras[inicio:fin])

                if len(fragmento.split()) < 2:
                    continue

                if fragmento in mensaje_normalizado:

                    coincidencias_parciales.append(
                        (len(fragmento), cuenta)
                    )
                    break

    if coincidencias_parciales:

        return max(coincidencias_parciales)[1]

    for alias in sorted(
        ALIAS_CUENTAS,
        key=len,
        reverse=True
    ):

        if normalizar_texto(alias) in mensaje_normalizado:

            cuenta_alias = ALIAS_CUENTAS[alias]

            for cuenta in cuentas_existentes:

                if normalizar_texto(cuenta) == normalizar_texto(cuenta_alias):

                    return cuenta

            return cuenta_alias

    return None


# ============================================================
# DETECTAR ANÁLISIS MENSUAL
# ============================================================

def detectar_analisis_mensual(mensaje):

    mensaje_normalizado = normalizar_texto(mensaje)

    frases = (
        "como voy",
        "como me fue",
        "analisis de gasto",
        "analiza mis gastos",
        "en que he gastado",
        "en que gasto",
        "que rubros he gastado mas",
        "rubros he gastado mas",
        "rubros gasto mas",
        "media de gasto",
        "que rubros deberia bajar",
        "que gastos deberia bajar",
        "gastos fijos",
        "gastos variables",
        "gastos ajustables",
        "gastos hormiga",
        "en que puedo recortar",
        "en que puedo ahorrar",
        "cuanto gasto en uber",
        "cuanto gaste en uber",
        "transporte de plataforma",
    )

    return any(frase in mensaje_normalizado for frase in frases)


# ============================================================
# DETECTAR CONCEPTO
# ============================================================

def detectar_concepto(
    mensaje,
    cuenta=None,
    subcategoria=None
):

    texto = normalizar_texto(
        mensaje
    )

    texto = (
        texto
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

        palabra = palabra.strip(
            "¿?¡!.,"
        )

        if palabra in PALABRAS_IGNORAR_CONCEPTO:

            continue

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
# DETECTAR STATUS
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

    for palabra in palabras_pendiente:

        if palabra in mensaje_normalizado:

            return "Pendiente"

    palabras_pagado = [
        "pagado",
        "pagados",
        "pagada",
        "pagadas",
    ]

    for palabra in palabras_pagado:

        if palabra in mensaje_normalizado:

            return "Pagado"

    return None


# ============================================================
# DETECTAR TIPO DE PAGO
# ============================================================

def detectar_tipo_pago(
    mensaje
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # "Próximos 3 meses" representa un periodo,
    # no una compra a meses.

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

    for palabra in palabras_meses:

        if palabra in mensaje_normalizado:

            return "Meses"

    if re.search(
        r"\b\d+\s+meses\b",
        mensaje_normalizado
    ):

        return "Meses"

    if "contado" in mensaje_normalizado:

        return "Contado"

    return None


# ============================================================
# INTERPRETAR REGISTRO DE ESTADO DE CUENTA
# ============================================================

def interpretar_estado_cuenta(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    if "estado" not in mensaje_normalizado:

        return None

    es_registro = False

    for palabra in PALABRAS_REGISTRO:

        if normalizar_texto(
            palabra
        ) in mensaje_normalizado:

            es_registro = True
            break

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

    if (
        mes is not None
        and anio is None
    ):

        anio = datetime.now().year

    monto = detectar_monto_estado_cuenta(
        mensaje
    )

    return {
        "cuenta": cuenta,
        "mes": mes,
        "anio": anio,
        "monto": monto,
    }


# ============================================================
# INTERPRETAR CONSULTA DE ESTADO DE CUENTA
# ============================================================

def interpretar_consulta_estado_cuenta(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    if "estado" not in mensaje_normalizado:

        return None

    es_registro = False

    for palabra in PALABRAS_REGISTRO:

        if normalizar_texto(
            palabra
        ) in mensaje_normalizado:

            es_registro = True
            break

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


# ============================================================
# BUSCAR ESTADO DE CUENTA
# ============================================================

def buscar_estado_cuenta(
    estados_cuenta,
    cuenta,
    mes,
    anio
):

    if (
        cuenta is None
        or mes is None
        or anio is None
    ):

        return None

    periodo_buscado = normalizar_texto(
        (
            f"{NOMBRES_MESES[mes]} "
            f"{anio}"
        )
    )

    # Recorremos al revés.
    # Si existe más de una importación,
    # usamos la más reciente.

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
# INTERPRETAR MENSAJE GENERAL
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

        periodos = detectar_proximos_meses(
            mensaje
        )

        periodo_relativo = detectar_periodo_relativo(
            mensaje
        )

        meses = detectar_meses(
            mensaje
        )

        anio = detectar_anio(
            mensaje
        )

        # Mayor prioridad:
        # próximos N meses

        if periodos:

            mes = None
            meses = []
            anio = None

        # Después:
        # este mes

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

        # Un mes escrito

        elif len(
            meses
        ) == 1:

            mes = meses[
                0
            ]

            if anio is None:

                anio = datetime.now().year

        # Varios meses escritos

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
        "analisis_mensual": detectar_analisis_mensual(mensaje),
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

        # ====================================================
        # TIPO DE MOVIMIENTO
        # ====================================================

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

        # ====================================================
        # FECHA DE PAGO
        # ====================================================

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

        # ====================================================
        # SUBCATEGORÍA
        # ====================================================

        if subcategoria is not None:

            valor_subcategoria = normalizar_texto(
                movimiento.get(
                    "Subcategoria",
                    ""
                )
            )

            if subcategoria == "Alimentación":
                from categorias import CATEGORIAS_ALIMENTACION
                coincide = valor_subcategoria in {
                    normalizar_texto(nombre)
                    for nombre in CATEGORIAS_ALIMENTACION
                }
            else:
                coincide = valor_subcategoria == normalizar_texto(subcategoria)

            if not coincide:

                continue

        # ====================================================
        # CUENTA
        # ====================================================

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

        # ====================================================
        # STATUS
        # ====================================================

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

        # ====================================================
        # TIPO DE PAGO
        # ====================================================

        if tipo_pago is not None:

            valor_tipo_pago = normalizar_texto(
                movimiento.get(
                    "Tipo de Pago",
                    ""
                )
            )

            if (
                valor_tipo_pago
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

    movimientos_filtrados = (
        obtener_movimientos_filtrados(
            movimientos,
            mes=mes,
            anio=anio,
            subcategoria=subcategoria,
            cuenta=cuenta,
            status=status,
            tipo_pago=tipo_pago,
            tipo_movimiento=tipo_movimiento
        )
    )

    total = 0.0

    for movimiento in movimientos_filtrados:

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


# ============================================================
# TOTAL PARA CONCILIACIÓN
# ============================================================
#
# IMPORTANTE:
#
# Ya NO exigimos que el día de pago coincida exactamente.
#
# Ejemplo:
#
# PDF Invex:
#   Fecha límite: 01/09/2026
#
# Histórico:
#   Fecha Pago: 02/09/2026
#
# Ambos pertenecen al mismo ciclo financiero.
#
# Por eso conciliamos usando:
#
#   Cuenta + Mes + Año
#
# ============================================================

def calcular_total_fecha_pago(
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

    total = 0.0

    for movimiento in movimientos:

        # Solo gastos

        tipo_movimiento = normalizar_texto(
            movimiento.get(
                "Tipo de Movimiento",
                ""
            )
        )

        if tipo_movimiento != "gasto":

            continue

        # Misma cuenta

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

        # Fecha del movimiento

        try:

            fecha_movimiento = convertir_fecha(
                movimiento.get(
                    "Fecha de Pago",
                    ""
                )
            )

        except ValueError:

            continue

        # ====================================================
        # MISMO MES Y AÑO
        # ====================================================

        if (
            fecha_movimiento.month
            != fecha_objetivo.month
        ):

            continue

        if (
            fecha_movimiento.year
            != fecha_objetivo.year
        ):

            continue

        # Sumar

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


# ============================================================
# MOVIMIENTOS DEL ESTADO PARA CONCILIACIÓN
# ============================================================

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

        # Solo gastos

        tipo_movimiento = normalizar_texto(
            movimiento.get(
                "Tipo de Movimiento",
                ""
            )
        )

        if tipo_movimiento != "gasto":

            continue

        # Misma cuenta

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

        try:

            fecha_movimiento = convertir_fecha(
                movimiento.get(
                    "Fecha de Pago",
                    ""
                )
            )

        except ValueError:

            continue

        # Conciliamos por MES + AÑO

        if (
            fecha_movimiento.month
            != fecha_objetivo.month
        ):

            continue

        if (
            fecha_movimiento.year
            != fecha_objetivo.year
        ):

            continue

        resultados.append(
            movimiento
        )

    return resultados


# ============================================================
# DIVIDIR MONTO EN PLAZOS
# ============================================================

def dividir_monto_en_plazos(
    monto_total,
    plazos,
    cuenta=None
):

    monto_total = Decimal(
        str(monto_total)
    )

    if plazos <= 1:

        return [
            float(
                monto_total.quantize(
                    Decimal("0.01")
                )
            )
        ]

    # ========================================================
    # BBVA PLATINUM
    # ========================================================
    #
    # BBVA redondea las parcialidades intermedias
    # a pesos enteros.
    #
    # La última cuota absorbe la diferencia para que
    # la suma de todas las parcialidades sea exactamente
    # igual al monto original.
    # ========================================================

    if cuenta == "BBVA Platinum":

        monto_teorico = (
            monto_total
            / Decimal(
                plazos
            )
        )

        monto_base = monto_teorico.quantize(
            Decimal("1"),
            rounding=ROUND_CEILING
        )

        montos = [
            monto_base
            for _ in range(
                plazos - 1
            )
        ]

        suma_anteriores = sum(
            montos,
            Decimal("0")
        )

        ultima_cuota = (
            monto_total
            - suma_anteriores
        )

        montos.append(
            ultima_cuota.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )
        )

        return [
            float(
                monto
            )
            for monto in montos
        ]

    # ========================================================
    # RESTO DE TARJETAS
    # ========================================================

    monto_base = (
        monto_total
        / Decimal(
            plazos
        )
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    montos = [
        monto_base
        for _ in range(
            plazos
        )
    ]

    diferencia = (
        monto_total
        - sum(
            montos,
            Decimal("0")
        )
    )

    montos[-1] = (
        montos[-1]
        + diferencia
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    return [
        float(
            monto
        )
        for monto in montos
    ]

# ============================================================
# GENERAR FECHAS DE PLAZOS
# ============================================================

def generar_fechas_plazos(
    fecha_inicial,
    plazos
):

    fechas = []

    for numero_plazo in range(
        plazos
    ):

        fecha = sumar_meses(
            fecha_inicial,
            numero_plazo
        )

        fechas.append(
            fecha
        )

    return fechas


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
        plazos,
        cuenta,
    )

    primera_fecha_pago = (
        calcular_primera_fecha_pago(
            fecha_compra,
            cuenta
        )
    )

    if primera_fecha_pago is None:

        raise ValueError(
            (
                "No existe configuración completa "
                "de corte y pago para la cuenta: "
                f"{cuenta}"
            )
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


# ============================================================
# FUNCIONES DE COMPATIBILIDAD
# ============================================================
#
# Las conservamos por si algún archivo o prueba antigua
# todavía utiliza los nombres anteriores.
# ============================================================

def convertir_mes_nombre(
    nombre_mes
):

    nombre_normalizado = normalizar_texto(
        nombre_mes
    )

    return MESES.get(
        nombre_normalizado
    )


def calcular_total_mes(
    movimientos,
    mes,
    anio
):

    return calcular_total(
        movimientos,
        mes=mes,
        anio=anio
    )


def calcular_total_categoria_mes(
    movimientos,
    mes,
    anio,
    subcategoria
):

    return calcular_total(
        movimientos,
        mes=mes,
        anio=anio,
        subcategoria=subcategoria
    )


def calcular_total_subcategoria(
    movimientos,
    subcategoria
):

    return calcular_total(
        movimientos,
        subcategoria=subcategoria
    )

# ============================================================
# PROYECCIÓN FINANCIERA v1.6.1
# ============================================================

def calcular_promedio_ingresos_recientes(movimientos, meses=3, hoy=None):
    """Promedio por Fecha de Pago de ingresos Pagado de meses completos.

    Los meses sin ingresos cuentan como cero. No aplica filtros de gastos.
    Pagado es el estado que asigna el bot al registrar un ingreso real.
    """
    if isinstance(meses, bool) or not isinstance(meses, int) or meses <= 0:
        raise ValueError("meses debe ser un entero positivo")
    hoy = hoy or datetime.now()
    fin = datetime(hoy.year, hoy.month, 1)
    inicio = sumar_meses(fin, -meses)
    total = Decimal("0")
    for movimiento in movimientos:
        if normalizar_texto(movimiento.get("Tipo de Movimiento", "")) != "ingreso":
            continue
        if normalizar_texto(movimiento.get("Status", "")) != "pagado":
            continue
        try:
            fecha = convertir_fecha(movimiento.get("Fecha de Pago", ""))
            if not inicio <= fecha < fin:
                continue
            monto = Decimal(str(convertir_monto(movimiento.get("Monto de Compra", 0))))
            if monto.is_finite():
                total += monto
        except (ValueError, TypeError):
            continue
    return float((total / meses).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ============================================================
# ANÁLISIS DE GASTO POR SUBCATEGORÍA
# ============================================================

def obtener_fecha_gasto(movimiento):
    """Fecha de compra; conserva compatibilidad con registros antiguos."""
    for campo in ("Fecha de Compra", "Fecha de Pago"):
        valor = movimiento.get(campo, "")
        if not valor:
            continue
        try:
            return convertir_fecha(valor)
        except (ValueError, TypeError):
            continue
    return None


def clasificar_flexibilidad_subcategoria(subcategoria):
    """Clasifica sólo cuando el nombre aporta evidencia suficiente."""
    texto = normalizar_texto(subcategoria)

    if not texto or texto == "sin clasificar":
        return "sin clasificar"

    compromisos = (
        "servicio", "seguro", "ppr", "retiro", "renta", "hipoteca",
        "prestamo", "colegiatura", "impuesto",
    )

    if any(palabra in texto for palabra in compromisos):
        return "compromiso/fijo"

    extraordinarios = (
        "viaje", "salud", "tercero", "reembolso", "regalo",
    )

    if any(palabra in texto for palabra in extraordinarios):
        return "extraordinario"

    return "ajustable"


def analizar_gasto_por_subcategoria(
    movimientos,
    mes=None,
    anio=None,
    meses_historial=3,
    cuenta=None,
    hoy=None,
):
    """Compara un mes de gasto con sus tres meses anteriores.

    Para el mes en curso compara el mismo número de días de cada mes
    anterior. Para un mes ya cerrado, compara meses completos.
    """
    if isinstance(meses_historial, bool) or not isinstance(meses_historial, int) or meses_historial <= 0:
        raise ValueError("meses_historial debe ser un entero positivo")

    hoy = hoy or datetime.now()
    mes = mes or hoy.month
    anio = anio or hoy.year
    inicio_objetivo = datetime(anio, mes, 1)
    es_mes_en_curso = (anio, mes) == (hoy.year, hoy.month)
    dia_comparable = hoy.day if es_mes_en_curso else calendar.monthrange(anio, mes)[1]

    periodos_referencia = [
        sumar_meses(inicio_objetivo, -desplazamiento)
        for desplazamiento in range(1, meses_historial + 1)
    ]

    totales = {}
    for fecha_periodo in [inicio_objetivo] + periodos_referencia:
        totales[(fecha_periodo.year, fecha_periodo.month)] = {}

    for movimiento in movimientos:
        if normalizar_texto(movimiento.get("Tipo de Movimiento", "")) != "gasto":
            continue
        if cuenta is not None and normalizar_texto(movimiento.get("Cuenta", "")) != normalizar_texto(cuenta):
            continue

        fecha = obtener_fecha_gasto(movimiento)
        if fecha is None or fecha.day > dia_comparable:
            continue

        periodo = (fecha.year, fecha.month)
        if periodo not in totales:
            continue

        try:
            monto = convertir_monto(movimiento.get("Monto de Compra", 0))
        except (ValueError, TypeError):
            continue

        subcategoria = str(movimiento.get("Subcategoria", "") or "Sin clasificar").strip()
        if not subcategoria:
            subcategoria = "Sin clasificar"
        acumulados = totales[periodo]
        acumulados[subcategoria] = acumulados.get(subcategoria, 0.0) + monto

    categorias = set()
    for acumulados in totales.values():
        categorias.update(acumulados)

    actual = totales[(anio, mes)]
    resultado_categorias = []
    for subcategoria in categorias:
        gasto_actual = round(actual.get(subcategoria, 0.0), 2)
        promedio = round(
            sum(totales[(fecha.year, fecha.month)].get(subcategoria, 0.0) for fecha in periodos_referencia)
            / meses_historial,
            2,
        )
        diferencia = round(gasto_actual - promedio, 2)
        porcentaje = round((diferencia / promedio) * 100, 1) if promedio else None
        resultado_categorias.append({
            "subcategoria": subcategoria,
            "actual": gasto_actual,
            "promedio": promedio,
            "diferencia": diferencia,
            "porcentaje": porcentaje,
            "flexibilidad": clasificar_flexibilidad_subcategoria(subcategoria),
        })

    resultado_categorias.sort(key=lambda categoria: (-categoria["actual"], categoria["subcategoria"]))
    total_actual = round(sum(actual.values()), 2)
    total_promedio = round(
        sum(sum(totales[(fecha.year, fecha.month)].values()) for fecha in periodos_referencia) / meses_historial,
        2,
    )

    return {
        "mes": mes,
        "anio": anio,
        "es_mes_en_curso": es_mes_en_curso,
        "dia_comparable": dia_comparable,
        "total_actual": total_actual,
        "total_promedio": total_promedio,
        "categorias": resultado_categorias,
    }


def formatear_fecha(fecha):
    """Día de dos dígitos, mes sin cero inicial y año de dos dígitos."""
    if not isinstance(fecha, datetime):
        fecha = convertir_fecha(fecha)
    return f"{fecha.day:02d}/{fecha.month}/{fecha.year % 100:02d}"
