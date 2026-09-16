import unittest
from unittest.mock import Mock, patch

from importar_estado import separar_concepto_y_descripcion
from sheets import obtener_movimientos, obtener_movimientos_sin_clasificar


class ConceptoImportacion(unittest.TestCase):

    def test_comercio_identificable_se_guarda_como_concepto(self):
        concepto, descripcion = separar_concepto_y_descripcion("NETFLIX.COM")

        self.assertEqual(concepto, "NETFLIX.COM")
        self.assertEqual(descripcion, "")

    def test_plataforma_generica_conserva_el_contexto(self):
        concepto, descripcion = separar_concepto_y_descripcion(
            "PAYPAL * Tienda Ejemplo"
        )

        self.assertEqual(concepto, "Tienda Ejemplo")
        self.assertEqual(descripcion, "PAYPAL * Tienda Ejemplo")

    def test_plataforma_sin_comercio_se_mantiene_en_descripcion(self):
        concepto, descripcion = separar_concepto_y_descripcion("MERCADO PAGO")

        self.assertEqual(concepto, "Mercado Pago")
        self.assertEqual(descripcion, "MERCADO PAGO")

    def test_rubro_conserva_compatibilidad_para_clasificar(self):
        hoja = Mock()
        hoja.get_all_records.return_value = [{"Rubro": "Transporte"}]
        hoja.get_all_values.return_value = [
            ["Tipo de Movimiento", "Rubro"],
            ["Gasto", "Sin clasificar"],
            ["Gasto", "Sin identificar"],
        ]

        with patch("sheets.obtener_hoja", return_value=hoja):
            movimientos = obtener_movimientos()
            pendientes = obtener_movimientos_sin_clasificar()

        self.assertEqual(movimientos[0]["Subcategoria"], "Transporte")
        self.assertEqual(pendientes[0]["Subcategoria"], "Sin clasificar")
        self.assertEqual(pendientes[1]["Subcategoria"], "Sin identificar")
