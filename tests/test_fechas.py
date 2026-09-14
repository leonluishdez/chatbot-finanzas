import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from finanzas import formatear_fecha, convertir_fecha
import sheets
from recurrentes_guiado import interpretar_inicio

class Fechas(unittest.TestCase):
    def test_formato_y_compatibilidad(self):
        for entrada in ('5/9/2026','05/09/26',datetime(2026,9,5)):
            self.assertEqual(formatear_fecha(entrada),'05/9/26')
        self.assertEqual(convertir_fecha('05/9/26'), datetime(2026,9,5))
        self.assertEqual(formatear_fecha('29/02/2028'),'29/2/28')
        self.assertEqual(interpretar_inicio('05/10/26',datetime(2026,9,13)),'2026-10')
    def test_escrituras_sheets_fechas_nativas(self):
        for funcion, getter, fila, indices, rango, lote in [
            (sheets.registrar_movimiento,'obtener_hoja',['Gasto','05/9/2026','01/9/26',460],(1,2),'B:C',False),
            (sheets.registrar_movimientos,'obtener_hoja',['Gasto','05/9/2026','',460],(1,2),'B:C',True),
            (sheets.registrar_estado_cuenta,'obtener_hoja_estados_cuenta',['Cuenta','septiembre 2026','05/9/2026','10/9/26',460],(2,3),'C:D',False),
            (sheets.registrar_estados_cuenta,'obtener_hoja_estados_cuenta',['Cuenta','septiembre 2026','05/9/2026','10/9/26',460],(2,3),'C:D',True)]:
            with self.subTest(funcion=funcion.__name__):
                original=list(fila);hoja=Mock()
                with patch.object(sheets,getter,return_value=hoja): funcion([fila] if lote else fila)
                hoja.format.assert_called_once_with(rango,{'numberFormat':{'type':'DATE','pattern':'dd/m/yy'}})
                llamada=hoja.append_rows if lote else hoja.append_row
                guardada=llamada.call_args.args[0]
                if lote: guardada=guardada[0]
                for i in indices:
                    if original[i]:
                        self.assertEqual(datetime(1899,12,30)+timedelta(days=guardada[i]),convertir_fecha(original[i]))
                    else: self.assertEqual(guardada[i],'')
                self.assertEqual(original,fila)
                self.assertEqual(guardada[-1],460)
    def test_fecha_invalida_no_escribe(self):
        hoja=Mock()
        with patch.object(sheets,'obtener_hoja',return_value=hoja):
            with self.assertRaises(ValueError): sheets.registrar_movimiento(['Gasto','31/2/26','',100])
        hoja.append_row.assert_not_called()
        hoja.format.assert_not_called()
