"""Interpretación opcional de consultas y registros de gastos con Gemini.

La IA nunca recibe movimientos completos ni escribe en Sheets.
Python valida su salida y ejecuta el flujo de confirmación del bot.
"""

import json
import math
import os
import re
from datetime import datetime

from finanzas import detectar_monto, normalizar_texto


MODELO_GEMINI = "gemini-3.5-flash-lite"


def es_candidato_registro_gasto(mensaje):
    """Limita Gemini a afirmaciones de gasto con un importe escrito."""
    texto = normalizar_texto(mensaje)
    return bool(
        re.search(r"\b(gaste|pague|compre)\b", texto)
        and not re.search(r"\b(cuanto|cuantos|total|consulta|consultar)\b", texto)
        and not re.search(r"\b(no|nunca)\b", texto)
        and "?" not in mensaje
        and detectar_monto(mensaje) is not None
    )


def interpretar_registro_gasto(mensaje, categorias=()):
    """Extrae monto, concepto y categoría sugerida; no autoriza el registro."""
    clave = os.getenv("GEMINI_API_KEY", "").strip()
    if not clave or not es_candidato_registro_gasto(mensaje):
        return None

    from google import genai
    from google.genai import types

    categorias_validas = {
        normalizar_texto(categoria): categoria
        for categoria in categorias
        if isinstance(categoria, str) and categoria.strip()
    }

    try:
        cliente = genai.Client(api_key=clave)
        respuesta = cliente.models.generate_content(
            model=MODELO_GEMINI,
            contents=(
                f"Categorías permitidas: "
                f"{json.dumps(list(categorias_validas.values()), ensure_ascii=False)}\n"
                f"Mensaje: {mensaje}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Interpreta una afirmación de un gasto personal en español. "
                    "Devuelve registrar_gasto solo si la persona dice que ya compró "
                    "o pagó algo y da un importe explícito. Para preguntas, "
                    "planes, ingresos o transferencias devuelve ninguna. "
                    "Extrae el importe exacto. El concepto debe ser una frase "
                    "breve que aparezca literalmente en el mensaje; no inventes "
                    "productos ni cuentas. Sugiere una categoría solo si encaja "
                    "claramente en la lista permitida; si hay duda usa null. "
                    "No respondas al usuario."
                ),
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "intencion": {"type": "STRING", "enum": ["registrar_gasto", "ninguna"]},
                        "monto": {"type": "NUMBER", "nullable": True},
                        "concepto": {"type": "STRING", "nullable": True},
                        "categoria": {"type": "STRING", "nullable": True},
                    },
                    "required": ["intencion", "monto", "concepto", "categoria"],
                },
            ),
        )
        datos = json.loads(respuesta.text)
    except Exception as error:
        print(f"Gemini: registro no disponible ({type(error).__name__})", flush=True)
        return None

    if not isinstance(datos, dict) or datos.get("intencion") != "registrar_gasto":
        return None
    monto = datos.get("monto")
    monto_local = detectar_monto(mensaje)
    if (
        type(monto) not in (int, float)
        or not math.isfinite(monto)
        or monto <= 0
        or monto_local is None
        or abs(monto - monto_local) >= 0.005
    ):
        return None
    concepto = datos.get("concepto")
    if (
        not isinstance(concepto, str)
        or not concepto.strip()
        or len(concepto.strip()) > 120
        or normalizar_texto(concepto.strip()) not in normalizar_texto(mensaje)
    ):
        return None
    categoria = datos.get("categoria")
    if isinstance(categoria, str):
        categoria = categorias_validas.get(normalizar_texto(categoria))
    else:
        categoria = None
    return {
        "intencion": "registrar_gasto",
        "monto": float(monto),
        "concepto": concepto.strip().capitalize(),
        "categoria": categoria,
    }


def interpretar_mensaje(mensaje, categorias=(), hoy=None):
    """Devuelve una intención y parámetros estructurados, o None sin clave/error.

    Solo se acepta ``consultar_gastos``. Ninguna respuesta del modelo puede
    registrar ni modificar movimientos.
    """
    clave = os.getenv("GEMINI_API_KEY", "").strip()
    if not clave or not mensaje or not mensaje.strip():
        return None

    from google import genai
    from google.genai import types

    hoy = hoy or datetime.now()
    categorias_validas = {
        normalizar_texto(categoria): categoria
        for categoria in categorias
        if isinstance(categoria, str) and categoria.strip()
    }
    opciones = list(categorias_validas.values())
    instruccion = (
        "Interpreta una consulta personal de gastos en español. "
        "Devuelve intencion=consultar_gastos solo si pide el total gastado; "
        "para registros, ingresos, análisis, proyecciones u otras peticiones "
        "devuelve intencion=ninguna. "
        "Elige categoria únicamente de la lista dada, o null. "
        "mes y anio deben ser null si no se mencionan. "
        "Para 'este mes' usa el mes y año actuales. "
        "Para un mes nombrado sin año usa el año actual. "
        "No inventes importes ni respondas la consulta."
    )
    try:
        cliente = genai.Client(api_key=clave)
        respuesta = cliente.models.generate_content(
            model=MODELO_GEMINI,
            contents=(
                f"Fecha actual: {hoy:%Y-%m-%d}\n"
                f"Categorías permitidas: {json.dumps(opciones, ensure_ascii=False)}\n"
                f"Mensaje: {mensaje}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=instruccion,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "intencion": {"type": "STRING", "enum": ["consultar_gastos", "ninguna"]},
                        "categoria": {"type": "STRING", "nullable": True},
                        "mes": {"type": "INTEGER", "nullable": True},
                        "anio": {"type": "INTEGER", "nullable": True},
                    },
                    "required": ["intencion", "categoria", "mes", "anio"],
                },
            ),
        )
        datos = json.loads(respuesta.text)
    except Exception as error:
        print(f"Gemini: llamada no disponible ({type(error).__name__})", flush=True)
        return None

    if not isinstance(datos, dict) or datos.get("intencion") != "consultar_gastos":
        return None
    mes, anio = datos.get("mes"), datos.get("anio")
    categoria = datos.get("categoria")
    if mes is not None and (type(mes) is not int or not 1 <= mes <= 12):
        return None
    if anio is not None and (type(anio) is not int or not 2000 <= anio <= hoy.year + 1):
        return None
    if (mes is None) != (anio is None):
        return None
    if categoria is not None:
        if not isinstance(categoria, str):
            return None
        categoria = categorias_validas.get(normalizar_texto(categoria))
        if categoria is None:
            return None
    if mes is None and categoria is None:
        return None
    return {
        "intencion": "consultar_gastos",
        "mes": mes,
        "anio": anio,
        "categoria": categoria,
    }
