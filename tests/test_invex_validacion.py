import copy
import unittest
from pathlib import Path

from importar_estado import validar_estado, preparar_movimientos_conciliacion_invex
from conciliar_movimientos import comparar_movimientos, preparar_movimientos_internos
from lector_estados import (
    extraer_datos_estado,
    extraer_movimientos_regulares_invex,
    extraer_resumen_cargos_abonos,
    extraer_texto_pdf,
)


ESTADOS = Path(__file__).resolve().parents[1] / "estados"


class ValidacionInvex(unittest.TestCase):
    def test_primera_cuota_sin_pdf(self):
        datos = {"cuenta": "Invex"}
        resumen = {
            "adeudo_anterior": 17829.25,
            "cargos_regulares": 0.0,
            "cargos_meses": 1939.95,
            "intereses": 1513.66,
            "comisiones": 0.0,
            "iva": 236.12,
            "pagos_abonos": 3332.50,
            "pago_no_intereses": 20027.98,
            "cuotas_msi_invex": [{
                "fecha": "02-Sep-2026", "original": 11049.0,
                "pendiente": 9207.50, "cuota": 1841.50, "numero": 1,
            }],
        }
        movimientos = [
            {"monto": -3332.50, "descripcion": "SU PAGO POR SPEI"},
            {"monto": 655.46, "descripcion": "VOLARISMXN 05 OF 11"},
            {"monto": 123.09, "descripcion": "PROMO 11 MSI 05 OF 11"},
            {"monto": 1161.40, "descripcion": "TRAS MSI 11 OF 11"},
            {"monto": 11049.0, "descripcion": "PROMO 6 MSI",
             "fecha_operacion": "02-Sep-2026"},
        ]
        self.assertTrue(validar_estado(datos, resumen, movimientos)["valido"])
        movimientos[-1]["fecha_operacion"] = "03-Sep-2026"
        self.assertFalse(validar_estado(datos, resumen, movimientos)["valido"])

    def cargar(self, nombre):
        ruta = ESTADOS / nombre
        if not ruta.exists():
            self.skipTest(f"No está disponible {nombre}")
        texto = extraer_texto_pdf(ruta)
        return (
            extraer_datos_estado(ruta),
            extraer_resumen_cargos_abonos(texto),
            extraer_movimientos_regulares_invex(texto),
        )

    def test_julio_y_agosto(self):
        for nombre, esperado in (
            ("Invex Julio 2026.pdf", 20534.79),
            ("Invex agosto 2026.pdf", 17829.25),
        ):
            with self.subTest(nombre=nombre):
                resultado = validar_estado(*self.cargar(nombre))
                self.assertTrue(resultado["valido"], resultado)
                self.assertEqual(resultado["calculado"], esperado)
                self.assertEqual(resultado["cuotas_nuevas_invex"], 0)

    def test_septiembre_y_bloqueos(self):
        datos, resumen, movimientos = self.cargar("Invex septiembre 2026.pdf")
        self.assertEqual(
            [(c["cuota"], c["numero"]) for c in resumen["cuotas_msi_invex"]],
            [(655.46, 5), (123.09, 5), (1841.50, 1)],
        )
        resultado = validar_estado(datos, resumen, movimientos)
        self.assertTrue(resultado["valido"], resultado)
        self.assertEqual(resultado["calculado"], 20027.98)
        self.assertEqual(resultado["cuotas_nuevas_invex"], 1841.50)

        conciliables = preparar_movimientos_conciliacion_invex(resumen, movimientos)
        compra = next(m for m in conciliables if m["monto"] == 11049.0)
        self.assertTrue(compra["origen_msi_confirmado"])
        cuota = next(m for m in conciliables if m.get("cuota_msi_tabla"))
        self.assertEqual(cuota["monto"], 1841.50)
        internos = preparar_movimientos_internos([{
            "Monto de Compra": 1841.50,
            "Tipo de Pago": "Meses",
            "Numero de Plazos": 6,
            "Descripcion": "Viaje programado",
        }])
        comparacion = comparar_movimientos(conciliables, internos)
        self.assertFalse(any(m["monto"] == 11049.0 for m in comparacion["solo_banco"]))
        self.assertEqual(len(comparacion["coincidencias"]), 1)
        self.assertEqual(comparacion["coincidencias"][0]["banco"]["monto"], 1841.50)

        internos_con_error = preparar_movimientos_internos([{
            "Monto de Compra": 11049.0,
            "Tipo de Pago": "Contado",
            "Descripcion": "PROMO 6 MSI",
        }, {
            "Monto de Compra": 1841.50,
            "Tipo de Pago": "Meses",
            "Numero de Plazos": 6,
            "Descripcion": "Viaje programado",
        }])
        con_error = comparar_movimientos(conciliables, internos_con_error)
        self.assertEqual([m["monto"] for m in con_error["solo_interno"]], [11049.0])

        sin_compra = [m for m in movimientos if m["monto"] != 11049.0]
        self.assertFalse(validar_estado(datos, resumen, sin_compra)["valido"])

        sin_cuota = copy.deepcopy(resumen)
        sin_cuota["cuotas_msi_invex"] = []
        self.assertFalse(validar_estado(datos, sin_cuota, movimientos)["valido"])

        cargos_incorrectos = copy.deepcopy(resumen)
        cargos_incorrectos["cargos_meses"] += 10
        self.assertFalse(validar_estado(datos, cargos_incorrectos, movimientos)["valido"])


if __name__ == "__main__":
    unittest.main()
