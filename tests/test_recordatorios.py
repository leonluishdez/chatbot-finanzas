import os
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import recordatorios
import bot


class Recordatorios(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "recordatorios.sqlite3"

    def movimientos(self):
        return [
            {"Tipo de Movimiento": "Gasto", "Status": "Pendiente", "Fecha de Pago": "15/9/26", "Monto de Compra": "460", "Cuenta": "Invex", "Descripcion": "Totalplay"},
            {"Tipo de Movimiento": "Gasto", "Status": "Pagado", "Fecha de Pago": "15/9/26", "Monto de Compra": "900", "Cuenta": "Invex", "Descripcion": "Ya pagado"},
            {"Tipo de Movimiento": "Ingreso", "Status": "Pendiente", "Fecha de Pago": "15/9/26", "Monto de Compra": "100", "Cuenta": "BBVA", "Descripcion": "Ingreso"},
            {"Tipo de Movimiento": "Gasto", "Status": "Pendiente", "Fecha de Pago": "16/9/26", "Monto de Compra": "10", "Cuenta": "Invex", "Descripcion": "Otro día"},
            {"Tipo de Movimiento": "Gasto", "Status": "Pendiente", "Fecha de Pago": "fecha inválida", "Monto de Compra": "10", "Cuenta": "Invex", "Descripcion": "Inválido"},
        ]

    def test_filtra_y_formatea(self):
        items = recordatorios.vencimientos_pendientes(self.movimientos(), date(2026, 9, 15))
        self.assertEqual(items, [{"descripcion": "Totalplay", "cuenta": "Invex", "monto": 460.0}])
        mensaje = recordatorios.crear_mensaje(date(2026, 9, 15), items)
        self.assertIn("15/9/26", mensaje)
        self.assertIn("$460.00", mensaje)
        self.assertIsNone(recordatorios.crear_mensaje(date(2026, 9, 15), []))

    def test_activar_desactivar_y_dedupe(self):
        self.assertEqual(recordatorios.chats_activos(self.ruta), [])
        recordatorios.activar(99, self.ruta)
        recordatorios.activar(99, self.ruta)
        self.assertEqual(recordatorios.chats_activos(self.ruta), [99])
        self.assertFalse(recordatorios.ya_enviado(99, "clave", self.ruta))
        recordatorios.marcar_enviado(99, "clave", self.ruta)
        self.assertTrue(recordatorios.ya_enviado(99, "clave", self.ruta))
        recordatorios.desactivar(99, self.ruta)
        self.assertEqual(recordatorios.chats_activos(self.ruta), [])

    async def test_no_marca_si_telegram_falla(self):
        recordatorios.activar(99, self.ruta)
        contexto = Mock()
        contexto.application.bot_data = {"obtener_movimientos": lambda: self.movimientos()}
        contexto.bot.send_message = AsyncMock(side_effect=OSError("sin red"))
        with patch.object(recordatorios, "ruta_datos", return_value=self.ruta), \
             patch("recordatorios.datetime") as fecha_hora:
            fecha_hora.now.return_value = Mock(date=lambda: date(2026, 9, 14))
            fecha_hora.combine.side_effect = __import__("datetime").datetime.combine
            with self.assertRaises(OSError):
                await recordatorios.enviar_recordatorios(contexto)
        self.assertFalse(recordatorios.ya_enviado(99, "vencimiento:2026-09-15", self.ruta))

    async def test_envia_una_vez_y_guarda_despues(self):
        recordatorios.activar(99, self.ruta)
        contexto = Mock()
        contexto.application.bot_data = {"obtener_movimientos": lambda: self.movimientos()}
        contexto.bot.send_message = AsyncMock()
        with patch.object(recordatorios, "ruta_datos", return_value=self.ruta), \
             patch("recordatorios.datetime") as fecha_hora:
            fecha_hora.now.return_value = Mock(date=lambda: date(2026, 9, 14))
            fecha_hora.combine.side_effect = __import__("datetime").datetime.combine
            await recordatorios.enviar_recordatorios(contexto)
            await recordatorios.enviar_recordatorios(contexto)
        contexto.bot.send_message.assert_awaited_once()
        self.assertTrue(recordatorios.ya_enviado(99, "vencimiento:2026-09-15", self.ruta))

    async def test_comando_activa_y_prueba_sin_enviar_automatico(self):
        update = Mock()
        update.effective_chat.id = 99
        update.message.text = "/recordatorios activar"
        update.message.reply_text = AsyncMock()
        with patch("bot.activar_recordatorios") as activar:
            await bot.manejar_recordatorios(update, Mock())
        activar.assert_called_once_with(99)
        self.assertIn("activados", update.message.reply_text.call_args.args[0])

        update.message.text = "/recordatorios probar"
        with patch("bot.obtener_movimientos", return_value=[]):
            await bot.manejar_recordatorios(update, Mock())
        self.assertEqual(update.message.reply_text.call_args.args[0], "No hay pagos pendientes para mañana.")
