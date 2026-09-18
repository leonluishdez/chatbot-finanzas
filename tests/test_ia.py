import json
import os
import unittest
from datetime import datetime
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


class RutaTelegram(unittest.IsolatedAsyncioTestCase):
    async def test_frases_de_consulta_usan_calculo_existente(self):
        movimientos = [{
            "Tipo de Movimiento": "Gasto", "Fecha de Compra": "10/08/2026",
            "Monto de Compra": "120", "Subcategoria": "Servicios",
        }]
        casos = (
            ("Cuánto gasté este mes", None, 9),
            ("Cuánto gasté en comida", "Comida", None),
            ("Cuánto gasté en comida en agosto", "Comida", 8),
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


if __name__ == "__main__":
    unittest.main()
