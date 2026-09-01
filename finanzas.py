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
}


ALIAS_CUENTAS = {

    "bbva platinum": "BBVA Platinum",
    "bbva plantinum": "BBVA Platinum",
    "plantinum": "BBVA Platinum",
    "platinum": "BBVA Platinum",

    "bbva debito": "BBVA Debito",

    "citibanamex oro": "Citibanamex Oro",
    "banamex oro": "Citibanamex Oro",

    "citibanamex costco": "Citibanamex Costco",
    "banamex costco": "Citibanamex Costco",
    "costco": "Citibanamex Costco",

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

def normalizar_texto(texto):

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
# MONTO
# ============================================================

def convertir_monto(monto):

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


# ============================================================
# FECHA
# ============================================================

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


# ============================================================
# INTENCIÓN
# ============================================================

def detectar_intencion(mensaje):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # Primero consultas.
    # Así "Cuánto gasté..." no se confunde
    # con registrar un gasto.

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

    # Registro explícito.

    for palabra in PALABRAS_REGISTRO:

        if normalizar_texto(
            palabra
        ) in mensaje_normalizado:

            return "registrar"

    # Registro natural de gastos.

    if "gaste" in mensaje_normalizado:

        monto = detectar_monto(
            mensaje
        )

        if monto is not None:

            return "registrar"

    # Registro natural de ingresos.

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


# ============================================================
# TIPO DE MOVIMIENTO
# ============================================================

def detectar_tipo_movimiento(mensaje):

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

def detectar_monto(mensaje):

    texto = normalizar_texto(
        mensaje
    )

    texto = (
        texto
        .replace("$", "")
        .replace(",", "")
    )

    # Quitar "6 meses", "12 MSI", etc.
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


# ============================================================
# PLAZOS
# ============================================================

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


# ============================================================
# MES INDIVIDUAL
# ============================================================

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

            return MESES[
                palabra
            ]

    return None


# ============================================================
# VARIOS MESES EXPLÍCITOS
# ============================================================

def detectar_meses(mensaje):

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

    ultimo_dia_mes = (
        calendar.monthrange(
            nuevo_anio,
            nuevo_mes
        )[1]
    )

    nuevo_dia = min(
        fecha.day,
        ultimo_dia_mes
    )

    return fecha.replace(
        year=nuevo_anio,
        month=nuevo_mes,
        day=nuevo_dia
    )


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
# SUBCATEGORÍA
# ============================================================

def detectar_subcategoria(
    mensaje,
    movimientos
):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

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

    for movimiento in movimientos:

        subcategoria = str(
            movimiento.get(
                "Subcategoria",
                ""
            )
        ).strip()

        if not subcategoria:

            continue

        if normalizar_texto(
            subcategoria
        ) in mensaje_normalizado:

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
# STATUS
# ============================================================

def detectar_status(mensaje):

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
# TIPO DE PAGO
# ============================================================

def detectar_tipo_pago(mensaje):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    # MUY IMPORTANTE:
    # "próximos 3 meses" habla del periodo
    # de consulta, no de una compra a meses.

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

    # También reconoce:
    # "compra a 6 meses"

    if re.search(
        r"\b\d+\s+meses\b",
        mensaje_normalizado
    ):

        return "Meses"

    if "contado" in mensaje_normalizado:

        return "Contado"

    return None


# ============================================================
# INTERPRETAR MENSAJE
# ============================================================

def interpretar_mensaje(
    mensaje,
    movimientos
):

    intencion = detectar_intencion(
        mensaje
    )

    tipo_movimiento = (
        detectar_tipo_movimiento(
            mensaje
        )
    )

    subcategoria = (
        detectar_subcategoria(
            mensaje,
            movimientos
        )
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

        # --------------------------------
        # PRÓXIMOS N MESES
        # --------------------------------

        periodos = detectar_proximos_meses(
            mensaje
        )

        # --------------------------------
        # PERIODO RELATIVO
        # --------------------------------

        periodo_relativo = (
            detectar_periodo_relativo(
                mensaje
            )
        )

        # --------------------------------
        # MESES ESCRITOS
        # --------------------------------

        meses = detectar_meses(
            mensaje
        )

        anio = detectar_anio(
            mensaje
        )

        # La prioridad más alta son
        # "los próximos N meses".

        if periodos:

            mes = None
            meses = []
            anio = None

        # Después "este mes".

        elif periodo_relativo is not None:

            mes = periodo_relativo[
                "mes"
            ]

            meses = [
                periodo_relativo[
                    "mes"
                ]
            ]

            anio = periodo_relativo[
                "anio"
            ]

        # Un solo mes escrito.

        elif len(meses) == 1:

            mes = meses[
                0
            ]

            if anio is None:

                anio = datetime.now().year

        # Varios meses escritos.

        elif len(meses) > 1:

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

        valor_tipo_movimiento = (
            normalizar_texto(
                movimiento.get(
                    "Tipo de Movimiento",
                    ""
                )
            )
        )

        if (
            valor_tipo_movimiento
            != normalizar_texto(
                tipo_movimiento
            )
        ):

            continue

        # --------------------------------
        # FECHA
        # --------------------------------

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

        # --------------------------------
        # SUBCATEGORÍA
        # --------------------------------

        if subcategoria is not None:

            valor = normalizar_texto(
                movimiento.get(
                    "Subcategoria",
                    ""
                )
            )

            if valor != normalizar_texto(
                subcategoria
            ):

                continue

        # --------------------------------
        # CUENTA
        # --------------------------------

        if cuenta is not None:

            valor = normalizar_texto(
                movimiento.get(
                    "Cuenta",
                    ""
                )
            )

            if valor != normalizar_texto(
                cuenta
            ):

                continue

        # --------------------------------
        # STATUS
        # --------------------------------

        if status is not None:

            valor = normalizar_texto(
                movimiento.get(
                    "Status",
                    ""
                )
            )

            if valor != normalizar_texto(
                status
            ):

                continue

        # --------------------------------
        # TIPO DE PAGO
        # --------------------------------

        if tipo_pago is not None:

            valor = normalizar_texto(
                movimiento.get(
                    "Tipo de Pago",
                    ""
                )
            )

            if valor != normalizar_texto(
                tipo_pago
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

    return total


# ============================================================
# MOTOR MSI
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
        - sum(montos),
        2
    )

    montos[-1] = round(
        montos[-1]
        + diferencia,
        2
    )

    return montos


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
# FECHA VÁLIDA
# ============================================================

def crear_fecha_valida(
    anio,
    mes,
    dia
):

    ultimo_dia = (
        calendar.monthrange(
            anio,
            mes
        )[1]
    )

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

    # Ejemplo:
    # Citibanamex Oro
    # corte 9, pago 29.
    # El pago cae en el mismo mes.

    if posible_pago > fecha_corte:

        return posible_pago

    # Ejemplo:
    # BBVA
    # corte 12, pago 3.
    # El pago cae en el siguiente mes.

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
# GENERAR CUOTAS
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
            "No existe configuración "
            "completa de corte y pago "
            f"para la cuenta: {cuenta}"
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