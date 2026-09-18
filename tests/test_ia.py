import json
import os
import fcntl
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import bot
import ia


class InterpretacionGemini(unittest.TestCase):
    def interpretar(self, salida):
        cliente = Mock()
        cliente.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps(salida)
        )
        with patch.dict(os.environ, {"GEMINI_API_KEY": "clave_de_prueba"}), patch(
            "google.genai.Client", return_value=cliente
        ):
            resultado = ia.interpretar_mensaje(
                "Cuánto gasté en comida en agosto",
                ["Comida", "Servicios"],
                hoy=datetime(2026, 9, 17),
            )
        return resultado, cliente

    def test_consulta_estructurada_sin_datos_financieros(self):
        resultado, cliente = self.interpretar({
            "intencion": "consultar_gastos", "categoria": "comida",
            "mes": 8, "anio": 2026,
        })
        self.assertEqual(resultado, {
            "intencion": "consultar_gastos", "categoria": "Comida",
            "mes": 8, "anio": 2026,
        })
        prompt = cliente.models.generate_content.call_args.kwargs["contents"]
        self.assertIn("Comida", prompt)
        self.assertNotIn("Monto de Compra", prompt)

    def test_rechaza_categoria_inventada_y_periodo_incompleto(self):
        for salida in (
            {"intencion": "consultar_gastos", "categoria": "Lujo", "mes": 8, "anio": 2026},
            {"intencion": "consultar_gastos", "categoria": "Comida", "mes": 8, "anio": None},
            {"intencion": "registrar_gasto", "categoria": "Comida", "mes": 8, "anio": 2026},
        ):
            with self.subTest(salida=salida):
                self.assertIsNone(self.interpretar(salida)[0])

    def test_sin_clave_no_llama_api(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            self.assertIsNone(ia.interpretar_mensaje("Cuánto gasté", ["Comida"]))

    def test_registro_extrae_solo_monto_y_concepto_escritos(self):
        cliente = Mock()
        cliente.models.generate_content.return_value = SimpleNamespace(text=json.dumps({
            "intencion": "registrar_gasto", "monto": 250, "concepto": "tacos",
            "categoria": "comida",
        }))
        with patch.dict(os.environ, {"GEMINI_API_KEY": "clave_de_prueba"}), patch(
            "google.genai.Client", return_value=cliente
        ):
            resultado = ia.interpretar_registro_gasto(
                "Pagué $250 por unos tacos", ["Comida", "Transporte"]
            )
        self.assertEqual(resultado, {
            "intencion": "registrar_gasto", "monto": 250.0, "concepto": "Tacos",
            "categoria": "Comida",
        })

    def test_categoria_fuera_de_lista_se_ignora(self):
        cliente = Mock()
        cliente.models.generate_content.return_value = SimpleNamespace(text=json.dumps({
            "intencion": "registrar_gasto", "monto": 250, "concepto": "tacos",
            "categoria": "Inventada",
        }))
        with patch.dict(os.environ, {"GEMINI_API_KEY": "clave_de_prueba"}), patch(
            "google.genai.Client", return_value=cliente
        ):
            resultado = ia.interpretar_registro_gasto("Pagué 250 por tacos", ["Comida"])
        self.assertIsNone(resultado["categoria"])

    def test_registro_rechaza_monto_o_concepto_inventado(self):
        for monto, concepto in ((300, "tacos"), (250, "hamburguesas"), (-250, "tacos")):
            with self.subTest(monto=monto, concepto=concepto):
                cliente = Mock()
                cliente.models.generate_content.return_value = SimpleNamespace(text=json.dumps({
                    "intencion": "registrar_gasto", "monto": monto, "concepto": concepto,
                }))
                with patch.dict(os.environ, {"GEMINI_API_KEY": "clave_de_prueba"}), patch(
                    "google.genai.Client", return_value=cliente
                ):
                    self.assertIsNone(ia.interpretar_registro_gasto("Pagué 250 por tacos"))

    def test_preguntas_y_negaciones_no_inician_registro(self):
        for mensaje in ("¿Cuánto pagué en tacos?", "¿Pagué 250 en tacos?", "No pagué 250 en tacos"):
            self.assertFalse(ia.es_candidato_registro_gasto(mensaje))


class RutaTelegram(unittest.IsolatedAsyncioTestCase):
    async def test_categoria_sugerida_puede_cambiarse_antes_de_guardar(self):
        update = Mock()
        update.message.text = "Pagué 250 por unos tacos"
        update.message.reply_text = AsyncMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        context = Mock(user_data={})
        with patch.object(bot, "obtener_movimientos", return_value=[]), patch.object(
            bot, "interpretar_registro_con_gemini", return_value={
                "intencion": "registrar_gasto", "monto": 250.0,
                "concepto": "Tacos", "categoria": "Restaurantes y cafeterías",
            }
        ), patch.object(bot, "registrar_movimiento") as guardar:
            await bot.responder_mensaje(update, context)
            self.assertEqual(context.user_data["gasto_pendiente"]["subcategoria"], "Restaurantes y cafeterías")
            update.callback_query.data = "cuenta:Invex"
            await bot.manejar_cuenta(update, context)
            self.assertIn("Categoría sugerida: Restaurantes y cafeterías", update.callback_query.edit_message_text.call_args.args[0])
            self.assertIn("Cambiar categoría", str(update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]))
            update.callback_query.data = "cambiar_categoria"
            await bot.cambiar_categoria(update, context)
            self.assertIn("Selecciona la categoría correcta", update.callback_query.edit_message_text.call_args.args[0])
            update.callback_query.data = "categoria:Por revisar"
            await bot.manejar_categoria(update, context)
            self.assertEqual(context.user_data["gasto_pendiente"]["categoria"], "Por revisar")
            self.assertIn("Categoría: Por revisar", update.callback_query.edit_message_text.call_args.args[0])
            guardar.assert_not_called()

    async def test_si_gemini_falla_no_crea_registro_nuevo(self):
        update = Mock()
        update.message.text = "Pagué 250 por unos tacos"
        update.message.reply_text = AsyncMock()
        context = Mock(user_data={})
        with patch.object(bot, "obtener_movimientos", return_value=[]), patch.object(
            bot, "interpretar_registro_con_gemini", return_value=None
        ), patch.object(bot, "registrar_movimiento") as guardar:
            await bot.responder_mensaje(update, context)
        self.assertNotIn("gasto_pendiente", context.user_data)
        self.assertIn("No pude preparar", update.message.reply_text.call_args.args[0])
        guardar.assert_not_called()

    async def test_gemini_inicia_flujo_pero_no_guarda_antes_de_confirmar(self):
        update = Mock()
        update.message.text = "Pagué 250 por unos tacos"
        update.message.reply_text = AsyncMock()
        context = Mock(user_data={})
        with patch.object(bot, "obtener_movimientos", return_value=[]), patch.object(
            bot, "interpretar_registro_con_gemini", return_value={
                "intencion": "registrar_gasto", "monto": 250.0, "concepto": "Tacos",
            }
        ), patch.object(bot, "registrar_movimiento") as guardar:
            await bot.responder_mensaje(update, context)
            pendiente = context.user_data["gasto_pendiente"]
            self.assertEqual((pendiente["monto"], pendiente["concepto"]), (250.0, "Tacos"))
            self.assertIn("Selecciona la tarjeta", update.message.reply_text.call_args.args[0])
            guardar.assert_not_called()

            update.callback_query.data = "cuenta:Invex"
            update.callback_query.answer = AsyncMock()
            update.callback_query.edit_message_text = AsyncMock()
            await bot.manejar_cuenta(update, context)
            update.callback_query.data = "categoria:Restaurantes y cafeterías"
            await bot.manejar_categoria(update, context)
            self.assertIn("Confirma el movimiento", update.callback_query.edit_message_text.call_args.args[0])
            guardar.assert_not_called()

    async def test_frases_de_consulta_usan_calculo_existente(self):
        movimientos = [{
            "Tipo de Movimiento": "Gasto", "Fecha de Compra": "10/08/2026",
            "Monto de Compra": "120", "Subcategoria": "Servicios",
        }]
        casos = (
            ("Cuánto gasté este mes", None, 9),
            ("Cuánto gasté en comida", "Alimentación", None),
            ("Cuánto gasté en comida en agosto", "Alimentación", 8),
        )
        for mensaje, categoria, mes in casos:
            with self.subTest(mensaje=mensaje):
                update = Mock()
                update.message.text = mensaje
                update.message.reply_text = AsyncMock()
                context = Mock(user_data={})
                with patch.object(bot, "obtener_movimientos", return_value=movimientos), patch.object(
                    bot, "interpretar_con_gemini", return_value={
                        "intencion": "consultar_gastos", "categoria": categoria,
                        "mes": mes, "anio": 2026 if mes else None,
                    }
                ), patch.object(bot, "calcular_total", return_value=120) as calcular:
                    await bot.responder_mensaje(update, context)
                self.assertEqual(calcular.call_args.kwargs["subcategoria"], categoria)
                self.assertEqual(calcular.call_args.kwargs["mes"], mes)
                self.assertIn("$120.00", update.message.reply_text.call_args.args[0])

    async def test_fallo_de_gemini_conserva_consulta_local(self):
        update = Mock()
        update.message.text = "Cuánto gasté este mes"
        update.message.reply_text = AsyncMock()
        context = Mock(user_data={})
        with patch.object(bot, "obtener_movimientos", return_value=[]), patch.object(
            bot, "interpretar_con_gemini", return_value=None
        ), patch.object(bot, "calcular_total", return_value=0) as calcular:
            await bot.responder_mensaje(update, context)
        self.assertEqual(calcular.call_args.kwargs["mes"], datetime.now().month)
        self.assertIn("No tienes gastos", update.message.reply_text.call_args.args[0])


class InstanciaUnica(unittest.TestCase):
    def test_segundo_proceso_no_adquiere_el_bloqueo(self):
        with TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "bot.lock"
            with ruta.open("a+") as primera_instancia:
                fcntl.flock(primera_instancia.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError, "otra instancia"):
                    bot.asegurar_instancia_unica(ruta)
            try:
                bot.asegurar_instancia_unica(ruta)
                self.assertIsNotNone(bot._archivo_instancia)
            finally:
                bot._archivo_instancia.close()
                bot._archivo_instancia = None


if __name__ == "__main__":
    unittest.main()
