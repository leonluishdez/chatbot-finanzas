import unittest
from datetime import datetime

from bot import crear_resumen_analisis_mensual
from finanzas import (
    analizar_gasto_por_subcategoria,
    detectar_analisis_mensual,
    detectar_cuenta,
    interpretar_mensaje,
)


HOY = datetime(2026, 9, 15)


def gasto(fecha, monto, subcategoria, cuenta="Caja Popular Mexicana", **extra):
    return {
        "Tipo de Movimiento": "Gasto",
        "Fecha de Compra": fecha,
        "Monto de Compra": monto,
        "Subcategoria": subcategoria,
        "Cuenta": cuenta,
        **extra,
    }


class AnalisisGastos(unittest.TestCase):

    def test_detecta_preguntas_sobre_rubros_media_y_ajustes(self):
        for mensaje in (
            "¿Qué rubros he gastado más este mes?",
            "¿Cuál es la media de gasto de este mes?",
            "¿Qué rubros debería bajar?",
        ):
            self.assertTrue(detectar_analisis_mensual(mensaje))

    def setUp(self):
        self.movimientos = [
            gasto("10/09/2026", 1500, "Comida"),
            gasto("20/09/2026", 9000, "Comida"),  # posterior al día comparable
            gasto("10/08/2026", 1000, "Comida"),
            gasto("20/08/2026", 500, "Comida"),
            gasto("10/07/2026", 1000, "Comida"),
            gasto("20/07/2026", 500, "Comida"),
            gasto("10/06/2026", 1000, "Comida"),
            gasto("20/06/2026", 500, "Comida"),
            gasto("10/05/2026", 1000, "Comida"),
            gasto("20/05/2026", 500, "Comida"),
            gasto("10/09/2026", 800, "Servicios"),
            gasto("10/08/2026", 500, "Servicios"),
            gasto("10/07/2026", 500, "Servicios"),
            gasto("10/06/2026", 500, "Servicios"),
        ]

    def test_cuenta_dinamica_por_nombre_parcial(self):
        cuenta = detectar_cuenta(
            "Cuánto tengo que pagar este mes de Caja Popular?",
            self.movimientos,
        )
        self.assertEqual(cuenta, "Caja Popular Mexicana")
        self.assertEqual(
            interpretar_mensaje("¿Cómo voy este mes de Caja Popular?", self.movimientos)["cuenta"],
            "Caja Popular Mexicana",
        )

    def test_mes_en_curso_compara_mismo_numero_de_dias(self):
        analisis = analizar_gasto_por_subcategoria(self.movimientos, hoy=HOY)
        comida = next(categoria for categoria in analisis["categorias"] if categoria["subcategoria"] == "Comida")
        self.assertTrue(analisis["es_mes_en_curso"])
        self.assertEqual(analisis["dia_comparable"], 15)
        self.assertEqual((comida["actual"], comida["promedio"], comida["diferencia"]), (1500, 1000, 500))

    def test_mes_cerrado_compara_meses_completos(self):
        analisis = analizar_gasto_por_subcategoria(self.movimientos, mes=8, anio=2026, hoy=HOY)
        comida = next(categoria for categoria in analisis["categorias"] if categoria["subcategoria"] == "Comida")
        self.assertFalse(analisis["es_mes_en_curso"])
        self.assertEqual(analisis["dia_comparable"], 31)
        self.assertEqual((comida["actual"], comida["promedio"]), (1500, 1500))

    def test_recomendaciones_separan_ajustables_y_fijos(self):
        texto = crear_resumen_analisis_mensual(self.movimientos, hoy=HOY)
        self.assertIn("💡 Ajustes concretos:", texto)
        self.assertIn("Comida: llevas $500.00", texto)
        self.assertIn("Compromisos que subieron:", texto)
        self.assertIn("Servicios: +$300.00", texto)


if __name__ == "__main__":
    unittest.main()
