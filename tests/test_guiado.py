import os
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, AsyncMock, patch
import recurrentes_guiado as g
from recurrentes import guardar_accion, leer_reglas
import bot

HOY = datetime(2026,9,13)
CUENTAS = ['Invex', 'BBVA Platinum']
CATEGORIAS = ['Servicios', 'Comida']

class Parser(unittest.TestCase):
    def test_totalplay(self):
        self.assertEqual(g.interpretar_registro('Registra un gasto recurrente de Totalplay por $460 al mes'),
                         {'concepto':'Totalplay', 'importe':'460.00'})
    def test_normales_no_interceptados(self):
        for t in ['Registra gasto de tacos por 100', 'Cuanto tengo pendiente', 'Cuanto gasto en recurrente']:
            self.assertIsNone(g.interpretar_registro(t))
    def test_invalidos(self):
        for t in ['Registra un gasto recurrente de Internet', 'Registra gasto recurrente de Internet por $0 al mes',
                  'Registra gasto recurrente de Internet por $500 al año']:
            with self.assertRaises(ValueError): g.interpretar_registro(t)
    def test_meses(self):
        self.assertEqual(g.interpretar_inicio('octubre', HOY), '2026-10')
        self.assertEqual(g.interpretar_inicio('enero', HOY), '2027-01')
        self.assertEqual(g.interpretar_inicio('octubre 2026', HOY), '2026-10')
        for t in ('2026-13','agosto 2026','2026-1','ayer'):
            with self.assertRaises(ValueError): g.interpretar_inicio(t, HOY)

class Flujo(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.context = Mock(user_data={})
        self.update = Mock()
        self.update.message.reply_text = AsyncMock()
        self.update.callback_query.answer = AsyncMock()
        self.update.callback_query.edit_message_text = AsyncMock()
    async def texto(self, t):
        self.update.message.text = t
        return await g.manejar_texto_recurrente(self.update,self.context,CUENTAS,CATEGORIAS,HOY)
    async def boton(self, accion, token=None):
        token = token or self.context.user_data[g.CLAVE]['token']
        self.update.callback_query.data = f'rec:{token}:{accion}'
        await g.manejar_boton_recurrente(self.update,self.context,CUENTAS,CATEGORIAS)
    async def iniciar(self):
        await self.texto('Registra un gasto recurrente de Totalplay por $460 al mes')
    async def completo(self):
        await self.iniciar()
        await self.boton('cuenta:0')
        await self.boton('categoria:0')
        await self.texto('15')
        await self.texto('2026-10')
    async def test_flujo_persistencia_solo_confirmar_y_doble_click(self):
        with TemporaryDirectory() as t:
            ruta = Path(t)/'reglas.sqlite3'
            with patch.object(g,'guardar_accion',side_effect=lambda a,p:guardar_accion(a,p,ruta,HOY)) as guardar:
                await self.completo()
                guardar.assert_not_called()
                self.assertEqual(leer_reglas(ruta), [])
                estado = self.context.user_data[g.CLAVE]
                token = estado['token']
                self.assertEqual(estado['cuenta'], 'Invex')
                self.assertEqual(estado['categoria'], 'Servicios')
                await self.boton('confirmar')
                await self.boton('confirmar', token)
                self.assertEqual(guardar.call_count, 1)
                self.assertEqual(len(leer_reglas(ruta)),1)
                self.assertNotIn(g.CLAVE,self.context.user_data)
    async def test_cancelar_sin_guardar(self):
        with patch.object(g,'guardar_accion') as guardar:
            await self.completo()
            await self.texto('cancelar')
            guardar.assert_not_called()
            self.assertNotIn(g.CLAVE,self.context.user_data)
    async def test_cancelar_boton(self):
        await self.iniciar()
        await self.boton('cancelar')
        self.assertNotIn(g.CLAVE,self.context.user_data)
    async def test_validacion_dia_mes(self):
        await self.iniciar()
        await self.boton('cuenta:0')
        await self.boton('categoria:0')
        await self.texto('32')
        self.assertEqual(self.context.user_data[g.CLAVE]['etapa'],'dia')
        await self.texto('31')
        await self.texto('2026-08')
        self.assertEqual(self.context.user_data[g.CLAVE]['etapa'],'inicio')
    async def test_boton_viejo_no_modifica_estado(self):
        await self.iniciar()
        await self.boton('cuenta:0','viejo')
        self.assertEqual(self.context.user_data[g.CLAVE]['etapa'],'cuenta')
        await self.boton('categoria:0')
        self.assertEqual(self.context.user_data[g.CLAVE]['etapa'],'cuenta')
    async def test_no_pisa_gasto_normal(self):
        self.context.user_data['gasto_pendiente']={'monto':100}
        await self.iniciar()
        self.assertNotIn(g.CLAVE,self.context.user_data)
        self.assertEqual(self.context.user_data['gasto_pendiente'],{'monto':100})
    async def test_error_guardado_no_anuncia_exito(self):
        await self.completo()
        with patch.object(g,'guardar_accion',side_effect=OSError('privado')):
            await self.boton('confirmar')
        texto = self.update.callback_query.edit_message_text.call_args.args[0]
        self.assertNotIn('privado',texto)
        self.assertIn('No pude',texto)
        self.assertIn(g.CLAVE,self.context.user_data)
    async def test_ruta_bot_antes_de_consultas(self):
        self.update.message.text = 'Registra un gasto recurrente de Totalplay por $460 al mes'
        with patch.object(bot,'obtener_movimientos',side_effect=AssertionError('No consultar Sheets')):
            await bot.responder_mensaje(self.update,self.context)
        self.assertEqual(self.context.user_data[g.CLAVE]['concepto'],'Totalplay')
