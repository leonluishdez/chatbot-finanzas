import unittest

from clasificacion import crear_vista_previa, sugerir_subcategoria


def gasto(descripcion="", subcategoria="Sin clasificar"):
    return {
        "Tipo de Movimiento": "Gasto",
        "Descripcion": descripcion,
        "Subcategoria": subcategoria,
    }


class Clasificacion(unittest.TestCase):
    def test_normaliza_categorias_equivalentes_con_alta_confianza(self):
        self.assertEqual(
            sugerir_subcategoria(gasto(subcategoria="NETFLIX")),
            ("Suscripciones", "alta", "Categoría existente normalizada"),
        )
        self.assertEqual(
            sugerir_subcategoria(gasto(subcategoria="Uber / Didi"))[0],
            "Transporte",
        )

    def test_patrones_solo_proponen_confianza_media(self):
        self.assertEqual(
            sugerir_subcategoria(gasto("Vuelo nacional")),
            ("Viajes", "media", "Patrón de descripción"),
        )
        self.assertEqual(
            sugerir_subcategoria(gasto("Comercio desconocido"))[1],
            "revision",
        )
        self.assertEqual(
            sugerir_subcategoria(gasto(subcategoria="REEMBOLSO"))[0],
            "Reembolsos recibidos",
        )

    def test_tambien_usa_concepto_cuando_descripcion_esta_vacia(self):
        movimiento = gasto("")
        movimiento["Concepto"] = "Uber Eats"

        self.assertEqual(
            sugerir_subcategoria(movimiento),
            ("Comida a domicilio", "media", "Patrón de descripción"),
        )

    def test_ignora_ingresos_y_resumen_no_expone_filas(self):
        ingreso = {"Tipo de Movimiento": "Ingreso", "Descripcion": "Nómina", "Subcategoria": "Nomina"}
        self.assertEqual(sugerir_subcategoria(ingreso), (None, "fuera_de_alcance", "No es un gasto"))
        vista = crear_vista_previa([gasto("Netflix"), gasto("Sin patrón"), ingreso])
        self.assertEqual(vista["por_confianza"], {"fuera_de_alcance": 1, "media": 1, "revision": 1})
        self.assertNotIn("Netflix", str(vista))


if __name__ == "__main__":
    unittest.main()
