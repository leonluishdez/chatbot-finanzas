import os
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from recurrentes import leer_reglas, guardar_accion, generar_vencimientos, procesar_comando
from bot import crear_resumen_proyeccion, manejar_recurrentes

HOY = datetime(2026, 9, 13)
PERIODOS = [{'anio': 2026, 'mes': 10}, {'anio': 2026, 'mes': 11}]


class Recurrentes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / 'reglas.sqlite3'

    def crear(self, concepto='Internet', cuenta='Invex', inicio='2026-10', dia='31'):
        return guardar_accion('crear', [concepto, '500', dia, cuenta, 'Servicios', inicio], self.ruta, HOY)

    def vencimientos(self, movimientos=(), periodos=PERIODOS):
        return generar_vencimientos(leer_reglas(self.ruta), movimientos, periodos, HOY)

    def test_lectura_sin_crear_archivos(self):
        self.assertEqual(leer_reglas(self.ruta), [])
        self.assertFalse(self.ruta.exists())

    def test_persistencia_y_duplicado(self):
        self.assertEqual(self.crear(), 1)
        self.assertEqual(leer_reglas(self.ruta)[0]['importe'], '500.00')
        with self.assertRaises(ValueError):
            self.crear(' INTERNET ', 'INVEX')
        self.assertEqual(len(leer_reglas(self.ruta)), 1)

    def test_pausar_activar_importe(self):
        self.crear()
        guardar_accion('pausar', ['1'], self.ruta)
        self.assertEqual(self.vencimientos(), [])
        guardar_accion('importe', ['1', '$650.25'], self.ruta)
        guardar_accion('activar', ['1'], self.ruta)
        self.assertEqual(self.vencimientos()[0]['Monto de Compra'], '650.25')

    def test_dias_y_anios(self):
        self.crear()
        periodos = [{'anio':2026,'mes':11}, {'anio':2027,'mes':2}, {'anio':2028,'mes':2}]
        self.assertEqual([m['Fecha de Pago'] for m in self.vencimientos(periodos=periodos)],
                         ['30/11/26', '28/2/27', '29/2/28'])

    def test_inicio_y_solo_futuros(self):
        self.crear(inicio='2026-11')
        self.assertEqual(len(self.vencimientos()), 1)
        self.assertEqual(self.vencimientos(periodos=[{'anio':2026,'mes':9}]), [])

    def test_consultas_repetidas_no_escriben(self):
        self.crear()
        antes = self.ruta.read_bytes()
        uno = self.vencimientos(periodos=PERIODOS + PERIODOS)
        self.assertEqual(len(uno), 2)
        self.assertEqual(uno, self.vencimientos())
        self.assertEqual(antes, self.ruta.read_bytes())

    def cargo(self, **extra):
        return {'Tipo de Movimiento':'Gasto', 'Status':'Pendiente', 'Tipo de Pago':'Contado',
                'Fecha de Pago':'05/10/2026', 'Cuenta':'Invex', 'Descripcion':'Internet',
                'Monto de Compra':550, 'Subcategoria':'Servicios', **extra}

    def test_cargo_real_sustituye_estimado_con_importe_distinto(self):
        self.crear()
        for status in ('Pendiente', 'Pagado'):
            with self.subTest(status=status):
                resultado = self.vencimientos([self.cargo(Status=status)])
                self.assertEqual(len(resultado), 1)
                self.assertEqual(resultado[0]['Fecha de Pago'], '30/11/26')

    def test_no_confunde_otra_cuenta_msi_o_nombre(self):
        self.crear()
        for extra in ({'Cuenta':'BBVA Platinum'}, {'Tipo de Pago':'Meses'},
                      {'Descripcion':'Otro'}, {'Tipo de Movimiento':'Ingreso'}):
            self.assertEqual(len(self.vencimientos([self.cargo(**extra)])), 2)

    def test_alias_exacto_y_conflicto(self):
        self.crear()
        guardar_accion('alias', ['1','PAGO INTERNET SA'], self.ruta)
        self.assertEqual(len(self.vencimientos([self.cargo(Descripcion='pago internet sa')])), 1)
        with self.assertRaises(ValueError):
            self.crear('PAGO INTERNET SA')
        self.crear('Telefono')
        with self.assertRaises(ValueError):
            guardar_accion('alias', ['2', 'PAGO INTERNET SA'], self.ruta)
        self.assertEqual(leer_reglas(self.ruta)[1]['alias'], [])

    def test_validacion_sin_escritura(self):
        for importe in ('-1', '0', 'nan', 'inf', 'x', '0.001'):
            with self.assertRaises(ValueError):
                guardar_accion('crear', ['Internet', importe, '15', 'Invex', 'Servicios', '2026-10'], self.ruta, HOY)
        for inicio in ('2026-08', '2026-13', '2026-1', '0000-01'):
            with self.assertRaises(ValueError):
                self.crear(inicio=inicio)
        for dia in ('0', '32', 'x'):
            with self.assertRaises(ValueError):
                self.crear(dia=dia)
        self.assertFalse(self.ruta.exists())

    def test_proyeccion_integra_y_filtra(self):
        self.crear()
        reglas = leer_reglas(self.ruta)
        texto = crear_resumen_proyeccion([self.cargo()], PERIODOS, status='Pendiente', hoy=HOY, reglas_recurrentes=reglas)
        self.assertIn('Total comprometido: $1,050.00', texto)
        self.assertEqual(texto.count('Incluye recurrentes estimados: $500.00'), 1)
        texto = crear_resumen_proyeccion([], PERIODOS, status='Pendiente', cuenta='Otra', hoy=HOY, reglas_recurrentes=reglas)
        self.assertIn('Total comprometido: $0.00', texto)
        self.assertNotIn('Incluye recurrentes', texto)
        texto = crear_resumen_proyeccion([], PERIODOS, status='Pendiente', tipo_pago='Meses', hoy=HOY, reglas_recurrentes=reglas)
        self.assertIn('Total comprometido: $0.00', texto)

    def test_consultas_historicas_no_cambian(self):
        self.crear()
        with patch('bot.leer_reglas', side_effect=AssertionError('No debe leer reglas')):
            texto = crear_resumen_proyeccion([], [{'mes':8,'anio':2026}], status='Pendiente', hoy=HOY)
        self.assertNotIn('recurrentes', texto)

    def test_comandos(self):
        respuesta = procesar_comando('/recurrentes crear Internet | 500 | 31 | Invex | Servicios | 2026-10', self.ruta, HOY)
        self.assertIn('1', respuesta)
        self.assertIn('Internet', procesar_comando('/recurrentes', self.ruta))
        procesar_comando('/recurrentes pausar 1', self.ruta)
        self.assertIn('Pausado', procesar_comando('/recurrentes listar', self.ruta))
        self.assertIn('descripción exacta', procesar_comando('/recurrentes ayuda', self.ruta))
        for comando in ('/recurrentes importe 1', '/recurrentes borrar 1', '/recurrentes activar 999'):
            with self.assertRaises(ValueError):
                procesar_comando(comando, self.ruta)


class TelegramRecurrentes(unittest.IsolatedAsyncioTestCase):
    async def test_handler_errores_y_respuesta(self):
        update = Mock()
        update.message.text = '/recurrentes'
        update.message.reply_text = AsyncMock()
        with patch('bot.procesar_comando', return_value='Reglas'):
            await manejar_recurrentes(update, Mock())
        update.message.reply_text.assert_awaited_with('Reglas')
        with patch('bot.procesar_comando', side_effect=ValueError('Formato inválido')):
            await manejar_recurrentes(update, Mock())
        self.assertIn('Formato inválido', update.message.reply_text.call_args.args[0])
        with patch('bot.procesar_comando', side_effect=OSError('dato privado')):
            await manejar_recurrentes(update, Mock())
        self.assertNotIn('dato privado', update.message.reply_text.call_args.args[0])
