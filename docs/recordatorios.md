# Recordatorios de pago

Actívalos desde el chat personal de Telegram:

```text
/recordatorios activar
```

El bot envía a las 9:00 a.m., hora de Ciudad de México, un aviso agrupado de los gastos con `Status = Pendiente` cuyo `Fecha de Pago` vence al día siguiente. Incluye descripción, cuenta, importe y total. Cada fecha se manda una sola vez, aun si el bot se reinicia.

Comandos:

```text
/recordatorios probar
/recordatorios desactivar
```

`probar` muestra el aviso que correspondería para mañana sin registrarlo como enviado. El comando solo activa o desactiva el chat desde el que se envía; no hay recordatorios para chats que no lo hayan activado.

Los recordatorios se guardan localmente en `.datos/recordatorios.sqlite3`, excluido de Git. No modifican movimientos ni estados de cuenta en Google Sheets. Si la Mac está apagada, dormida o sin internet a las 9:00 a.m., ese aviso no se recupera automáticamente; el bot debe estar en funcionamiento para enviarlo.
