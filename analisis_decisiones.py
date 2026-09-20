"""Cálculos verificables para recomendaciones de gasto.

La IA puede interpretar la pregunta, pero los importes siempre se calculan
localmente a partir de los movimientos de Google Sheets.
"""

from collections import defaultdict
from datetime import datetime

from finanzas import convertir_fecha, convertir_monto, normalizar_texto


REGLAS_CATEGORIA = {
    "Viajes": ("Especial", 0),
    "Compras de terceros": ("Especial", 0),
    "Restaurantes y cafeterías": ("Variable ajustable", 0.25),
    "Comida a domicilio": ("Variable ajustable", 0.30),
    "Supermercado y despensa": ("Variable necesario", 0.05),
    "Transporte": ("Variable necesario", 0.15),
    "Vivienda y servicios": ("Fijo esencial", 0),
    "Telefonía e internet": ("Fijo esencial", 0.10),
    "Suscripciones": ("Fijo ajustable", 0.30),
    "Salud y medicamentos": ("Variable necesario", 0),
    "Cuidado personal y bienestar": ("Variable ajustable", 0.15),
    "Ropa y accesorios": ("Variable ajustable", 0.20),
    "Tecnología": ("Variable ajustable", 0.15),
    "Compras personales": ("Variable ajustable", 0.25),
    "Hogar": ("Variable necesario", 0.05),
    "Educación": ("Variable necesario", 0.05),
    "Entretenimiento": ("Variable ajustable", 0.25),
    "Seguros": ("Fijo esencial", 0),
    "Regalos": ("Variable ajustable", 0.10),
    "Mascotas": ("Variable necesario", 0.05),
    "Ahorro y retiro": ("Ahorro y meta", 0),
    "Préstamos y deudas": ("Deuda", 0),
    "Comisiones e intereses": ("Costo financiero evitable", 0.50),
    "Trámites e impuestos": ("Fijo esencial", 0),
    "Servicios familiares": ("Especial", 0),
    "Por revisar": ("Especial", 0),
}


def clasificar_movimiento(movimiento, categoria):
    """Clasifica compromisos conocidos que requieren detalle por comercio."""
    texto = normalizar_texto(
        f"{movimiento.get('Concepto', '')} {movimiento.get('Descripcion', '')}"
    )
    es_allianz = "allianz" in texto
    es_ppr = es_allianz and (
        "ppr" in texto
        or "daf plus" in texto
        or categoria == "Ahorro y retiro"
    )
    es_gmm = es_allianz and (
        "pl retail" in texto
        or "domi retail" in texto
        or categoria in {"Seguros", "Salud y medicamentos"}
    )
    if es_ppr:
        return "Fijo esencial", 0, "PPR Allianz"
    if es_gmm:
        return "Fijo esencial", 0, "Seguro de gastos médicos Allianz"
    tipo, porcentaje = REGLAS_CATEGORIA.get(categoria, ("Especial", 0))
    return tipo, porcentaje, categoria


def analizar_decisiones(movimientos, mes=None, anio=None, hoy=None, limite_hormiga=300):
    hoy = hoy or datetime.now()
    mes, anio = mes or hoy.month, anio or hoy.year
    por_categoria = defaultdict(float)
    por_tipo = defaultdict(float)
    por_tipo_detalle = defaultdict(lambda: defaultdict(float))
    ahorro_retiro = 0.0
    fijos_pendientes = defaultdict(float)
    transporte = defaultdict(float)
    transporte_cantidad = defaultdict(int)
    hormiga_por_categoria = defaultdict(lambda: {"cantidad": 0, "total": 0.0})
    hormiga_total = 0.0
    hormiga_cantidad = 0

    for movimiento in movimientos:
        if normalizar_texto(movimiento.get("Tipo de Movimiento")) != "gasto":
            continue
        if normalizar_texto(movimiento.get("Status")) != "pagado":
            continue
        try:
            fecha = convertir_fecha(movimiento.get("Fecha de Pago", ""))
            monto = convertir_monto(movimiento.get("Monto de Compra", 0))
        except (TypeError, ValueError):
            continue
        if (fecha.year, fecha.month) != (anio, mes):
            continue

        categoria = str(movimiento.get("Subcategoria", "") or "Por revisar").strip()
        tipo, porcentaje, etiqueta = clasificar_movimiento(movimiento, categoria)
        por_categoria[categoria] += monto
        por_tipo[tipo] += monto
        por_tipo_detalle[tipo][etiqueta] += monto
        if categoria == "Ahorro y retiro":
            ahorro_retiro += monto

        if "ajustable" in tipo.lower() and monto <= limite_hormiga:
            hormiga_total += monto
            hormiga_cantidad += 1
            hormiga_por_categoria[categoria]["cantidad"] += 1
            hormiga_por_categoria[categoria]["total"] += monto

        if categoria == "Transporte":
            texto = normalizar_texto(
                f"{movimiento.get('Concepto', '')} {movimiento.get('Descripcion', '')}"
            )
            if "uber" in texto or "didi" in texto:
                transporte["plataforma"] += monto
                transporte_cantidad["plataforma"] += 1
            elif "misaldo" in texto or "misaldosfin" in texto or "mi saldo" in texto:
                transporte["publico"] += monto
                transporte_cantidad["publico"] += 1
            else:
                transporte["otro"] += monto
                transporte_cantidad["otro"] += 1

    for movimiento in movimientos:
        if normalizar_texto(movimiento.get("Tipo de Movimiento")) != "gasto":
            continue
        if normalizar_texto(movimiento.get("Status")) != "pendiente":
            continue
        try:
            fecha = convertir_fecha(movimiento.get("Fecha de Pago", ""))
            monto = convertir_monto(movimiento.get("Monto de Compra", 0))
        except (TypeError, ValueError):
            continue
        if (fecha.year, fecha.month) != (anio, mes):
            continue
        categoria = str(movimiento.get("Subcategoria", "") or "Por revisar").strip()
        tipo, _, etiqueta = clasificar_movimiento(movimiento, categoria)
        if tipo == "Fijo esencial":
            fijos_pendientes[etiqueta] += monto

    oportunidades = []
    for categoria, total in por_categoria.items():
        tipo, porcentaje = REGLAS_CATEGORIA.get(categoria, ("Especial", 0))
        potencial = round(total * porcentaje, 2)
        if potencial > 0:
            oportunidades.append({
                "categoria": categoria,
                "tipo": tipo,
                "total": round(total, 2),
                "porcentaje": porcentaje,
                "potencial": potencial,
            })
    oportunidades.sort(key=lambda item: (-item["potencial"], item["categoria"]))

    fuera = por_categoria["Restaurantes y cafeterías"] + por_categoria["Comida a domicilio"]
    supermercado = por_categoria["Supermercado y despensa"]
    especial = por_tipo["Especial"]
    total = sum(por_categoria.values())
    return {
        "mes": mes,
        "anio": anio,
        "por_categoria": {k: round(v, 2) for k, v in por_categoria.items()},
        "por_tipo": {k: round(v, 2) for k, v in por_tipo.items()},
        "por_tipo_detalle": {
            tipo: {etiqueta: round(total, 2) for etiqueta, total in detalles.items()}
            for tipo, detalles in por_tipo_detalle.items()
        },
        "ahorro_retiro": round(ahorro_retiro, 2),
        "fijos_pendientes": {
            etiqueta: round(total, 2) for etiqueta, total in fijos_pendientes.items()
        },
        "total": round(total, 2),
        "gasto_personal": round(total - especial, 2),
        "comida_fuera": round(fuera, 2),
        "supermercado": round(supermercado, 2),
        "hormiga_total": round(hormiga_total, 2),
        "hormiga_cantidad": hormiga_cantidad,
        "hormiga_por_categoria": {
            categoria: {
                "cantidad": valores["cantidad"],
                "total": round(valores["total"], 2),
            }
            for categoria, valores in hormiga_por_categoria.items()
        },
        "transporte": {k: round(v, 2) for k, v in transporte.items()},
        "transporte_cantidad": dict(transporte_cantidad),
        "oportunidades": oportunidades,
        "ahorro_sugerido": round(sum(x["potencial"] for x in oportunidades), 2),
    }


def detectar_tipo_analisis(mensaje):
    """Distingue la pregunta para evitar responder siempre con el resumen largo."""
    texto = normalizar_texto(mensaje)
    if any(palabra in texto for palabra in ("uber", "didi", "plataforma", "transporte publico")):
        return "transporte"
    if "hormiga" in texto:
        return "hormiga"
    if (
        "fijos" in texto
        or "fijo" in texto
        or "variables" in texto
        or "variable" in texto
    ):
        return "estructura"
    if any(frase in texto for frase in ("recortar", "puedo ahorrar", "deberia bajar", "ajustables")):
        return "recortes"
    return "resumen"
