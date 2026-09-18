"""Interpretación opcional de consultas de gastos con Gemini.

La IA recibe nombres de categorías, nunca importes ni movimientos completos.
Python valida su salida antes de que el bot consulte Sheets.
"""

import json
import os
from datetime import datetime

from finanzas import normalizar_texto


MODELO_GEMINI = "gemini-3.5-flash-lite"


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
    except Exception:
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
