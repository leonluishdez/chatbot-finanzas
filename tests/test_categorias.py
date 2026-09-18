import unittest

from categorias import CATEGORIAS_ALIMENTACION, CATEGORIAS_GASTO, CATEGORIAS_INGRESO
from finanzas import detectar_subcategoria, obtener_movimientos_filtrados


class CategoriasNuevas(unittest.TestCase):
    def test_las_listas_son_distintas_y_sin_comida_generica(self):
        self.assertNotIn("Comida", CATEGORIAS_GASTO)
        self.assertIn("Restaurantes y cafeterías", CATEGORIAS_GASTO)
        self.assertIn("Comida a domicilio", CATEGORIAS_GASTO)
        self.assertIn("Viajes", CATEGORIAS_GASTO)
        self.assertIn("Compras de terceros", CATEGORIAS_GASTO)
        self.assertIn("Transferencias recibidas", CATEGORIAS_INGRESO)

    def test_comida_consulta_las_tres_categorias(self):
        movimientos = [
            {"Tipo de Movimiento": "Gasto", "Subcategoria": categoria, "Fecha de Pago": "10/09/2026"}
            for categoria in CATEGORIAS_ALIMENTACION
        ] + [
            {"Tipo de Movimiento": "Gasto", "Subcategoria": "Viajes", "Fecha de Pago": "10/09/2026"}
        ]
        filtro = detectar_subcategoria("¿Cuánto gasté en comida?", movimientos)
        self.assertEqual(filtro, "Alimentación")
        self.assertEqual(len(obtener_movimientos_filtrados(movimientos, subcategoria=filtro)), 3)
        self.assertEqual(
            detectar_subcategoria("¿Cuánto gasté en comida a domicilio?", movimientos),
            "Comida a domicilio",
        )


if __name__ == "__main__":
    unittest.main()
