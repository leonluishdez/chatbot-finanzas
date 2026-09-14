import unittest
from datetime import datetime
from test_regresion import movimiento
from finanzas import calcular_promedio_ingresos_recientes as promedio
from bot import crear_resumen_proyeccion as resumen

HOY = datetime(2026, 9, 13)

class Proyeccion(unittest.TestCase):
    def setUp(self):
        self.ingresos = [movimiento(monto=24000), movimiento(fecha='01/07/2026', monto=28000),
                         movimiento(fecha='31/08/2026', monto=23000)]

    def test_tres_meses_completos(self):
        datos = self.ingresos + [movimiento(fecha='01/09/2026', monto=999999),
                                movimiento(fecha='31/05/2026', monto=999999),
                                movimiento(status='Pendiente', monto=999999),
                                movimiento('Pago', monto=999999), movimiento('Devolucion', monto=999999)]
        self.assertEqual(promedio(datos, hoy=HOY), 25000)

    def test_sin_historial_y_meses_en_cero(self):
        self.assertEqual(promedio([], hoy=HOY), 0)
        self.assertEqual(promedio([movimiento(monto=3000)], hoy=HOY), 1000)

    def test_cambio_anio(self):
        datos = [movimiento(fecha=f'15/{mes}/2025', monto=3000) for mes in (10, 11, 12)]
        datos += [movimiento(fecha='01/01/2026', monto=999999)]
        self.assertEqual(promedio(datos, hoy=datetime(2026, 1, 1)), 3000)

    def test_importes_y_fechas_invalidos(self):
        datos = [movimiento(monto='$3,000.00'), movimiento(monto='mal'),
                 movimiento(monto='NaN'), movimiento(monto='inf'), movimiento(fecha='mal')]
        self.assertEqual(promedio(datos, hoy=HOY), 1000)

    def test_redondeo(self):
        self.assertEqual(promedio([movimiento(monto=100)], hoy=HOY), 33.33)
        for meses in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                promedio([], meses=meses, hoy=HOY)

    def test_disponible_y_total(self):
        datos = self.ingresos + [movimiento('Gasto', '01/10/2026', 30000, 'Pendiente'),
                                movimiento('Gasto', '01/10/2026', 500, 'Pagado')]
        texto = resumen(datos, [{'mes':10, 'anio':2026}, {'mes':11, 'anio':2026}], status='Pendiente', hoy=HOY)
        for esperado in ['Ingreso mensual estimado: $25,000.00', 'Comprometido: $30,000.00',
                         'Disponible estimado: $-5,000.00', 'Disponible estimado: $25,000.00',
                         'Ingreso estimado del periodo: $50,000.00', 'Disponible estimado del periodo: $20,000.00']:
            self.assertIn(esperado, texto)

    def test_filtro_no_reduce_ingreso(self):
        datos = self.ingresos + [movimiento('Gasto', '01/10/2026', 100, 'Pendiente', Cuenta='Invex'),
                                movimiento('Gasto', '01/10/2026', 200, 'Pendiente', Cuenta='Otra')]
        texto = resumen(datos, [{'mes':10,'anio':2026}], cuenta='Invex', status='Pendiente', hoy=HOY)
        self.assertIn('Disponible estimado: $24,900.00', texto)
        self.assertIn('solo descuenta los gastos seleccionados', texto)

    def test_otros_tipos_y_periodos_conservan_salida(self):
        for periodos, status, tipo in [([{'mes':10,'anio':2026}], 'Pagado', 'Gasto'),
                                      ([{'mes':10,'anio':2026}], None, 'Ingreso'),
                                      ([{'mes':8,'anio':2026}], 'Pendiente', 'Gasto'),
                                      ([{'mes':9,'anio':2026}], 'Pendiente', 'Gasto'),
                                      ([], 'Pendiente', 'Gasto')]:
            self.assertNotIn('Disponible estimado', resumen(self.ingresos, periodos, status=status, tipo_movimiento=tipo, hoy=HOY))
