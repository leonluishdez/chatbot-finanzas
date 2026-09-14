import os
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
import unittest
from datetime import datetime
from unittest.mock import Mock, patch
import bot
import finanzas as f
import sheets
import lector_estados as lector
import importar_estado as importar
import conciliar_movimientos as conciliar
import revisar_estado


def movimiento(tipo='Ingreso', fecha='15/06/2026', monto=24000, status='Pagado', **extra):
    return {'Tipo de Movimiento': tipo, 'Fecha de Pago': fecha,
            'Monto de Compra': monto, 'Status': status, **extra}


class Regresion(unittest.TestCase):
    def test_multibanco(self):
        for texto, cuenta in [('costco banamex', 'Citibanamex Costco'),
                              ('oro banamex', 'Citibanamex Oro'),
                              ('invex', 'Invex'), ('bbva platinum', 'BBVA Platinum')]:
            self.assertEqual(lector.detectar_cuenta_estado(texto), cuenta)
            cuotas = f.generar_cuotas(1200, 3, datetime(2026, 8, 15), 'Compra', cuenta)
            self.assertEqual(len(cuotas), 3)
            self.assertAlmostEqual(sum(c['monto'] for c in cuotas), 1200, places=2)
            self.assertEqual(len({(c['fecha'].year, c['fecha'].month) for c in cuotas}), 3)

    def test_cuotas_importadas(self):
        resultado = importar.detectar_cuota_en_descripcion('COMERCIO 001 de 003')
        self.assertTrue(resultado['es_cuota'])
        self.assertEqual((resultado['numero'], resultado['plazos']), (1, 3))
        self.assertFalse(importar.detectar_cuota_en_descripcion('COMERCIO')['es_cuota'])

    def test_conciliacion_uno_a_uno(self):
        cargo = {'descripcion': 'COMERCIO', 'monto': 100}
        resultado = conciliar.comparar_movimientos([cargo, cargo], [cargo])
        self.assertEqual(len(resultado['coincidencias']), 1)
        self.assertEqual(len(resultado['solo_banco']), 1)
        self.assertEqual(resultado['solo_interno'], [])

    def test_clasificar_sin_red(self):
        hoja = Mock()
        hoja.get_all_values.return_value = [
            ['Tipo de Movimiento', 'Subcategoria'],
            ['Gasto', 'Sin clasificar'], ['Ingreso', 'Sin clasificar'], ['Gasto', 'Comida']]
        with patch.object(sheets, 'obtener_hoja', return_value=hoja):
            filas = sheets.obtener_movimientos_sin_clasificar()
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['_fila'], 2)

    def test_consultas(self):
        datos = f.interpretar_mensaje('Cuanto tengo pendiente los proximos 6 meses', [])
        self.assertEqual(datos['status'], 'Pendiente')
        self.assertEqual(len(datos['periodos']), 6)
        self.assertEqual(f.detectar_intencion('Cuanto gaste en viajes'), 'consultar')

    def test_resumen_historico(self):
        texto = bot.crear_resumen_proyeccion(
            [movimiento('Gasto', monto=100)], [{'mes': 6, 'anio': 2026}], status='Pagado')
        self.assertEqual(texto, '📊 Compromisos próximos\n\nJunio: $100.00\n\nTotal comprometido: $100.00')


if __name__ == '__main__':
    unittest.main()
