import calendar
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
# CONFIGURACIÓN DE TARJETAS
# =============================

CONFIGURACION_TARJETAS = {

    "BBVA Platinum": {
        "dia_corte": 12,
        "dia_pago": 3,
    },

    # IMPORTANTE:
    # Aquí vuelve a colocar los valores
    # que tú ya tienes configurados.

    "Citibanamex Oro": {
        "dia_corte": 8,
        "dia_pago": 28,
    },

    "Citibanamex Costco": {
        "dia_corte": 8,
        "dia_pago": 28,
    },

    "Invex": {
        "dia_corte": 12,
        "dia_pago": 2,
    },
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

    # BBVA Platinum
    "bbva platinum": "BBVA Platinum",
    "bbva plantinum": "BBVA Platinum",
    "plantinum": "BBVA Platinum",
    "platinum": "BBVA Platinum",
    "bbva": "BBVA Platinum",

    # BBVA Débito
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
# PALABRAS QUE NO FORMAN
# PARTE DE LA DESCRIPCIÓN
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


# =============================
# NORMALIZAR TEXTO
# =============================

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


# =============================
# CONVERTIR MONTO
# =============================

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


# =============================
# CONVERTIR FECHA
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
        f"Formato de fecha no reconocido: "
        f"{fecha_texto}"
    )


# =============================
# DETECTAR INTENCIÓN
# =============================

def detectar_intencion(mensaje):

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
    ]

    for palabra in palabras_consulta:

        if palabra in mensaje_normalizado:

            return "consultar"

    # -------------------------
    # REGISTRO EXPLÍCITO
    # -------------------------

    for palabra in PALABRAS_REGISTRO:

        if normalizar_texto(
            palabra
        ) in mensaje_normalizado:

            return "registrar"

    # -------------------------
    # REGISTRO NATURAL
    # DE GASTOS
    # -------------------------

    if "gaste" in mensaje_normalizado:

        monto = detectar_monto(
            mensaje
        )

        if monto is not None:

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

    for palabra in palabras_ingreso_registro:

        if palabra in mensaje_normalizado:

            monto = detectar_monto(
                mensaje
            )

            if monto is not None:

                return "registrar"

    return "consultar"


# =============================
# DETECTAR TIPO MOVIMIENTO
# =============================

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


# =============================
# DETECTAR MONTO
# =============================

def detectar_monto(mensaje):

    texto = normalizar_texto(
        mensaje
    )

    texto = (
        texto
        .replace("$", "")
        .replace(",", "")
    )

    # Quitamos primero expresiones
    # como 6 meses o 12 MSI para no
    # confundirlas con el monto.
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

    # Primero alias conocidos.
    # Los más largos tienen prioridad.
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

    # Después cuentas históricas
    # existentes en Sheets.
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


# =============================
# DETECTAR CONCEPTO
# =============================

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


# =============================
# DETECTAR STATUS
# =============================

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


# =============================
# DETECTAR TIPO DE PAGO
# =============================

def detectar_tipo_pago(mensaje):

    mensaje_normalizado = normalizar_texto(
        mensaje
    )

    if (
        "meses" in mensaje_normalizado
        or "msi" in mensaje_normalizado
    ):

        return "Meses"

    if "contado" in mensaje_normalizado:

        return "Contado"

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
    anio = None
    monto = None
    concepto = ""
    plazos = 1

    # =============================
    # REGISTRO
    # =============================

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

        # Si estamos registrando un
        # ingreso y "Comisiones",
        # por ejemplo, ya fue detectado
        # como subcategoría, lo usamos
        # también como descripción.
        if (
            tipo_movimiento == "Ingreso"
            and not concepto
            and subcategoria is not None
        ):

            concepto = subcategoria

    # =============================
    # CONSULTA
    # =============================

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
        "tipo_pago": tipo_pago,
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
    tipo_pago=None,
    tipo_movimiento="Gasto"
):

    total = 0.0

    for movimiento in movimientos:

        # -------------------------
        # TIPO DE MOVIMIENTO
        # -------------------------

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

        # -------------------------
        # FECHA
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

        # -------------------------
        # CUENTA
        # -------------------------

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

        # -------------------------
        # STATUS
        # -------------------------

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

        # -------------------------
        # TIPO DE PAGO
        # -------------------------

        if tipo_pago is not None:

            valor_tipo_pago = (
                normalizar_texto(
                    movimiento.get(
                        "Tipo de Pago",
                        ""
                    )
                )
            )

            if (
                valor_tipo_pago
                != normalizar_texto(
                    tipo_pago
                )
            ):

                continue

        # -------------------------
        # MONTO
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

    return total


# ============================================================
# MOTOR DE MSI
# ============================================================


# =============================
# DIVIDIR MONTO
# =============================

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


# =============================
# SUMAR MESES
# =============================

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


# =============================
# GENERAR FECHAS SIMPLES
# =============================

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


# =============================
# CREAR FECHA VÁLIDA
# =============================

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


# =============================
# CALCULAR FECHA DE CORTE
# =============================

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

    # Si compramos antes o
    # el mismo día del corte,
    # entra al corte de ese mes.
    if fecha_compra.day <= dia_corte:

        return crear_fecha_valida(
            fecha_compra.year,
            fecha_compra.month,
            dia_corte
        )

    # Si compramos después del
    # corte, entra en el siguiente.
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


# =============================
# PRIMERA FECHA DE PAGO
# =============================

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

    # Primero vemos si el día de pago
    # queda después del corte dentro
    # del mismo mes.
    posible_pago = crear_fecha_valida(
        fecha_corte.year,
        fecha_corte.month,
        dia_pago
    )

    if posible_pago > fecha_corte:

        return posible_pago

    # Si el día de pago es menor
    # al día de corte, corresponde
    # al mes siguiente.
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


# =============================
# GENERAR CUOTAS MSI REALES
# =============================

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
            "No existe una configuración "
            f"completa de corte y pago "
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