import unittest
from datetime import datetime

from analisis_decisiones import analizar_decisiones, detectar_tipo_analisis
from bot import crear_respuesta_analisis_especifico


def gasto(monto, categoria, concepto="", status="Pagado", fecha="10/09/2026"):
    return {
        "Tipo de Movimiento": "Gasto",
        "Fecha de Pago": fecha,
        "Monto de Compra": monto,
        "Concepto": concepto,
        "Descripcion": "",
        "Subcategoria": categoria,
        "Status": status,
    }


class AnalisisDecisiones(unittest.TestCase):
    def test_separa_plataforma_transporte_publico_y_pendientes(self):
        datos = analizar_decisiones([
            gasto(200, "Transporte", "Uber Trip"),
            gasto(100, "Transporte", "Conekta*MiSaldosfinmx"),
            gasto(500, "Transporte", "Uber Trip", status="Pendiente"),
        ], mes=9, anio=2026)
        self.assertEqual(datos["transporte"], {"plataforma": 200.0, "publico": 100.0})
        self.assertEqual(datos["total"], 300.0)

    def test_calcula_hormiga_comida_y_ahorro_sugerido(self):
        datos = analizar_decisiones([
            gasto(200, "Restaurantes y cafeterías", "Café"),
            gasto(400, "Comida a domicilio", "Uber Eats"),
            gasto(1000, "Supermercado y despensa", "Walmart"),
            gasto(600, "Compras de terceros", "Vuelo familiar"),
        ], mes=9, anio=2026, hoy=datetime(2026, 9, 19))
        self.assertEqual(datos["hormiga_total"], 200.0)
        self.assertEqual(datos["comida_fuera"], 600.0)
        self.assertEqual(datos["supermercado"], 1000.0)
        self.assertEqual(datos["gasto_personal"], 1600.0)
        self.assertEqual(datos["ahorro_sugerido"], 220.0)

    def test_allianz_ppr_y_gmm_son_fijos_esenciales(self):
        ppr = gasto(2074, "Ahorro y retiro", "ALLIANZ MEXICO CR")
        gmm = gasto(1532.59, "Salud y medicamentos", "ALLIANZ PL RETAIL 3DS")
        ppr_pendiente = gasto(2074, "Ahorro y retiro", "ALLIANZ MEXICO CR", status="Pendiente")
        datos = analizar_decisiones([ppr, gmm, ppr_pendiente], mes=9, anio=2026)

        self.assertEqual(datos["por_tipo"]["Fijo esencial"], 3606.59)
        self.assertEqual(datos["por_tipo_detalle"]["Fijo esencial"], {
            "PPR Allianz": 2074.0,
            "Seguro de gastos médicos Allianz": 1532.59,
        })
        self.assertEqual(datos["ahorro_retiro"], 2074.0)
        self.assertEqual(datos["fijos_pendientes"], {"PPR Allianz": 2074.0})

    def test_respuesta_acepta_filtro_cuenta_del_flujo_principal(self):
        texto = crear_respuesta_analisis_especifico(
            "Muéstrame mis gastos hormiga",
            [gasto(200, "Restaurantes y cafeterías", "Café")],
            mes=9,
            anio=2026,
            cuenta=None,
        )
        self.assertIn("Gastos pequeños ajustables", texto)

    def test_distingue_consultas_especificas(self):
        casos = {
            "Analiza mis gastos": "resumen",
            "¿En qué puedo recortar?": "recortes",
            "Muéstrame mis gastos hormiga": "hormiga",
            "¿Cuánto gasté en Uber?": "transporte",
            "¿Cuáles son mis gastos fijos y variables?": "estructura",
        }
        for mensaje, esperado in casos.items():
            with self.subTest(mensaje=mensaje):
                self.assertEqual(detectar_tipo_analisis(mensaje), esperado)


if __name__ == "__main__":
    unittest.main()
