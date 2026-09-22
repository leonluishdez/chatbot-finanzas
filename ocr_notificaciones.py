"""OCR local y extracción conservadora de alertas bancarias."""

from pathlib import Path
import re

from finanzas import normalizar_texto

CUENTAS_POR_BANCO = (
    (("bbva",), "BBVA Platinum"),
    (("citibanamex", "banamex", "costco"), "Citibanamex Costco"),
    (("invex",), "Invex"),
)

PATRONES_MONTO = (
    re.compile(r"(?:compra|cargo|consumo|pago|operacion|operación)\s+(?:por|de)?\s*\$\s*([\d,]+(?:\.\d{2})?)", re.I),
    re.compile(r"(?:compra|cargo|consumo|pago|operacion|operación)\s+(?:por|de)\s+([\d,]+(?:\.\d{2})?)", re.I),
    re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)"),
    re.compile(r"(?:monto|importe)[^\d]{0,12}([\d,]+(?:\.\d{2})?)", re.I),
)


def extraer_texto_imagen(ruta):
    from rapidocr import RapidOCR

    resultado = RapidOCR()(str(ruta))
    textos = getattr(resultado, "txts", None) or ()
    return "\n".join(textos).strip()


def _extraer_monto(texto):
    for patron in PATRONES_MONTO:
        coincidencia = patron.search(texto)
        if coincidencia:
            try:
                return float(coincidencia.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def _extraer_cuenta(texto):
    normalizado = normalizar_texto(texto)
    for alias, cuenta in CUENTAS_POR_BANCO:
        if any(nombre in normalizado for nombre in alias):
            return cuenta
    return None


def _extraer_concepto(texto):
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]
    patrones = (
        re.compile(r"\b(?:en|comercio|establecimiento)\s*[:\-]?\s*(.+)$", re.I),
        re.compile(r"(?:concepto|descripcion|descripción)\s*[:\-]?\s*(.+)$", re.I),
    )
    descartes = (
        "saldo", "tarjeta", "terminacion", "terminación", "fecha", "hora",
        "monto", "importe", "disponible", "notificacion", "notificación",
        "compra realizada", "autorizada", "autorizado", "banco",
        "compra", "cargo", "consumo", "pago", "operacion", "operación",
    )
    candidatos = []
    for linea in lineas:
        for patron in patrones:
            coincidencia = patron.search(linea)
            if coincidencia:
                candidatos.append((3, coincidencia.group(1)))
                break

        normalizado = normalizar_texto(linea)
        if (
            len(linea) >= 3
            and len(linea) <= 80
            and not any(x in normalizado for x in descartes)
            and not re.search(r"(?:\$|\b\d[\d,.]*\b|https?://|[*#]{2,})", linea)
            and not re.search(r"\b(?:visa|mastercard|amex|credito|cr[eé]dito|d[eé]bito)\b", normalizado)
        ):
            candidatos.append((1, linea))

    for _, valor in sorted(candidatos, key=lambda item: -item[0]):
        valor = re.sub(r"\s+", " ", valor).strip(" .:-–—")
        if valor and not any(x in normalizar_texto(valor) for x in descartes):
            return valor[:80]
    return ""


def interpretar_alerta(texto):
    return {
        "monto": _extraer_monto(texto),
        "concepto": _extraer_concepto(texto),
        "cuenta": _extraer_cuenta(texto),
        "texto": texto,
    }
