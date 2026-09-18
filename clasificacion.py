"""Propuesta reversible de categorías para movimientos ya registrados.

Este módulo no escribe en Google Sheets. Sólo transforma una fila en una
sugerencia y una confianza para que el cambio posterior pueda revisarse.
"""

from collections import Counter

from categorias import CATEGORIAS_GASTO, CATEGORIAS_INGRESO
from finanzas import normalizar_texto


CATEGORIA_SIN_IDENTIFICAR = "Por revisar"


ALIAS_CATEGORIAS = {
    "viajes": "Viajes",
    "uber / didi": "Transporte",
    "uber/didi": "Transporte",
    "transporte": "Transporte",
    "ropa y accesorios": "Compras personales",
    "restaurantes": "Restaurantes y cafeterías",
    "restaurantes y comida": "Restaurantes y cafeterías",
    "supermercado": "Supermercado y despensa",
    "plan de retiro": "Ahorro y retiro",
    "ppr": "Ahorro y retiro",
    "retiro / ppr": "Ahorro y retiro",
    "fondo emergencias": "Ahorro y retiro",
    "seguro de vida": "Seguros y protección",
    "seguro de gmm": "Seguros y protección",
    "seguro de viaje": "Seguros y protección",
    "netflix": "Suscripciones",
    "meli+": "Suscripciones",
    "suscripcion": "Suscripciones",
    "amazon prime": "Suscripciones",
    "apple one": "Suscripciones",
    "apple music": "Suscripciones",
    "google fotos": "Suscripciones",
    "google one": "Suscripciones",
    "hbo max": "Suscripciones",
    "icloud": "Suscripciones",
    "spotify": "Suscripciones",
    "vclub": "Suscripciones",
    "wal mart pass": "Suscripciones",
    "uber pass": "Suscripciones",
    "plan telefonico": "Vivienda y servicios",
    "servicios": "Vivienda y servicios",
    "didi food/ubereats/rappi": "Comida a domicilio",
    "didifood/ubereats/rappi": "Comida a domicilio",
    "conciertos": "Entretenimiento",
    "cine": "Entretenimiento",
    "entretenimiento": "Entretenimiento",
    "salud": "Salud y cuidado personal",
    "medicamentos": "Salud y cuidado personal",
    "suplementos": "Salud y cuidado personal",
    "cuidado personal": "Salud y cuidado personal",
    "amazon": "Compras personales",
    "regalos": "Regalos",
    "art. hogar": "Hogar",
    "serv. hogar": "Hogar",
    "renta": "Vivienda y servicios",
    "anualidad": "Comisiones e intereses",
    "invex cero": "Comisiones e intereses",
    "vexi": "Comisiones e intereses",
    "comisiones pt": "Comisiones e intereses",
    "reembolso": "Reembolsos recibidos",
    "cursos": "Educación",
}


REGLAS_DESCRIPCION = (
    (("netflix", "spotify", "hbo", "paramount", "apple one", "apple music", "google one", "google cloud", "icloud", "amazon prime", "chat gpt", "dominio "), "Suscripciones"),
    (("vuelo", "hotel", "asiento vuelo", "volaris"), "Viajes"),
    (("uber eats", "ubereats", "didi food", "didifood", "rappi"), "Comida a domicilio"),
    (("uber", "didi"), "Transporte"),
    (("prestamo", "abono deuda"), "Préstamos y deudas"),
    (("reembolso", "devolucion"), "Reembolsos recibidos"),
    (("ahorro",), "Ahorro y retiro"),
    (("paquete funerario",), "Servicios y compromisos familiares"),
    (("anualidad", "iva sobre comisiones", "interes compras"), "Comisiones e intereses"),
    (("colchon", "cable macbook"), "Hogar"),
    (("airpods", "nintendo", "playera", "lentes", "springfield"), "Compras personales"),
    (("boletos", "u2.com", "barcelona"), "Entretenimiento"),
)


def sugerir_subcategoria(movimiento):
    """Devuelve categoría, confianza y fundamento sin modificar la fila."""
    tipo = normalizar_texto(movimiento.get("Tipo de Movimiento", ""))
    actual = normalizar_texto(movimiento.get("Subcategoria", ""))
    if tipo == "ingreso":
        for categoria in CATEGORIAS_INGRESO:
            if normalizar_texto(categoria) == actual:
                return categoria, "alta", "Categoría vigente"
        ingresos_anteriores = {
            "nomina": "Sueldo",
            "bono producto": "Bonos y prestaciones",
            "aguinaldo": "Bonos y prestaciones",
            "prima vacacional": "Bonos y prestaciones",
            "utilidades": "Bonos y prestaciones",
            "comisiones": "Comisiones laborales",
            "comisiones pt": "Comisiones laborales",
            "reembolso": "Reembolsos y devoluciones",
        }
        categoria = ingresos_anteriores.get(actual, "Ingresos por revisar")
        confianza = "alta" if actual in ingresos_anteriores else "revision"
        return categoria, confianza, "Ingreso anterior normalizado"
    if tipo != "gasto":
        return None, "fuera_de_alcance", "Tipo de movimiento desconocido"
    for categoria in CATEGORIAS_GASTO:
        if normalizar_texto(categoria) == actual:
            return categoria, "alta", "Categoría vigente"
    if actual in ALIAS_CATEGORIAS:
        return ALIAS_CATEGORIAS[actual], "alta", "Categoría existente normalizada"

    # Las importaciones nuevas guardan el comercio en Concepto y usan
    # Descripcion sólo cuando hace falta contexto adicional. Para registros
    # anteriores alguno de los dos campos puede estar vacío.
    descripcion = normalizar_texto(
        " ".join(
            str(movimiento.get(campo, "") or "")
            for campo in ("Concepto", "Descripcion")
        )
    )
    for patrones, categoria in REGLAS_DESCRIPCION:
        if any(patron in descripcion for patron in patrones):
            return categoria, "media", "Patrón de descripción"

    return CATEGORIA_SIN_IDENTIFICAR, "revision", "Sin patrón suficientemente claro"


def crear_vista_previa(movimientos):
    """Resume resultados sin devolver descripciones ni datos de cada fila."""
    por_confianza = Counter()
    por_categoria = Counter()
    por_origen = Counter()

    for movimiento in movimientos:
        categoria, confianza, origen = sugerir_subcategoria(movimiento)
        por_confianza[confianza] += 1
        if categoria:
            por_categoria[categoria] += 1
        por_origen[origen] += 1

    return {
        "total": len(movimientos),
        "por_confianza": dict(sorted(por_confianza.items())),
        "por_categoria": dict(sorted(por_categoria.items(), key=lambda item: (-item[1], item[0]))),
        "por_origen": dict(sorted(por_origen.items(), key=lambda item: (-item[1], item[0]))),
    }
