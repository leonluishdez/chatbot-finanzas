import unittest

from ocr_notificaciones import interpretar_alerta


class OcrNotificacionesTests(unittest.TestCase):
    def test_extrae_alerta_bbva(self):
        datos = interpretar_alerta(
            "BBVA\nCompra por $1,234.50\nen RESTAURANTE CENTRAL\nTarjeta terminación 1234"
        )
        self.assertEqual(datos["monto"], 1234.50)
        self.assertEqual(datos["concepto"], "RESTAURANTE CENTRAL")
        self.assertEqual(datos["cuenta"], "BBVA Platinum")

    def test_no_confunde_hora_con_monto(self):
        datos = interpretar_alerta("Notificación bancaria\nCompra rechazada\n08:55")
        self.assertIsNone(datos["monto"])

    def test_no_toma_la_palabra_mensaje_como_comercio(self):
        datos = interpretar_alerta("Ocurrió un error al procesar tu mensaje")
        self.assertEqual(datos["concepto"], "")

    def test_detecta_citibanamex(self):
        datos = interpretar_alerta("Citibanamex\nCargo $207.40\nComercio: UBER")
        self.assertEqual(datos["cuenta"], "Citibanamex Costco")
        self.assertEqual(datos["concepto"], "UBER")
