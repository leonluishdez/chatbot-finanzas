# Gastos recurrentes mensuales

## Registro guiado

Escribe «Registra un gasto recurrente de Totalplay por $460 al mes» con tus datos reales. El bot pregunta cuenta y categoría con botones, luego día de pago (1–31) y mes inicial (AAAA-MM o nombre del mes y año). Finalmente muestra un resumen con botones Confirmar y Cancelar. También puedes escribir «cancelar» durante el flujo. La regla se guarda solamente al confirmar. Un reinicio descarta los formularios sin confirmar, pero conserva las reglas guardadas.

El registro guiado requiere la palabra recurrente y actualmente admite periodicidad mensual. No crea un gasto real en Sheets ni calcula el día de pago desde el corte de la tarjeta. Los comandos anteriores siguen disponibles.

En Telegram, `/recurrentes ayuda` muestra los comandos. Ejemplo con datos ficticios (sustituir antes de enviar):

```text
/recurrentes crear Internet | 500 | 15 | Invex | Servicios | 2026-10
/recurrentes
/recurrentes importe 1 | 550
/recurrentes pausar 1
/recurrentes activar 1
/recurrentes alias 1 | DESCRIPCION EXACTA DEL BANCO
```

Cada regla tiene concepto, importe mensual, día de pago, cuenta, subcategoría y mes inicial. Usa los nombres de cuenta y subcategoría de Sheets. El día corresponde al pago, no a la compra ni al corte de la tarjeta. Si no existe ese día, se usa el último del mes.

Las reglas se aplican a la consulta existente de gastos pendientes de próximos meses, por ejemplo «Cuánto tengo pendiente los próximos 6 meses». Se muestran como «Incluye recurrentes estimados». No afectan ingresos, consultas históricas, MSI, importadores ni filas de Sheets. Las estimaciones se calculan al consultar; no requieren un proceso programado ni escriben cargos futuros. No se proyectan en el mes actual.

## Sustitución por cargos reales

Un gasto registrado Pendiente o Pagado sustituye la estimación del mismo mes de Fecha de Pago cuando coinciden la cuenta y la descripción (o Concepto si falta Descripcion). Se normalizan acentos y mayúsculas. El importe puede ser diferente: manda el cargo real. Los movimientos con Tipo de Pago Meses no sustituyen recurrentes.

Si el banco utiliza otra descripción, agrega esa descripción exacta como alias. No se hace coincidencia aproximada por monto o texto: mientras el nombre no coincida, pueden aparecer tanto el cargo real como la estimación. La conciliación bancaria sigue usando exclusivamente los movimientos reales de Sheets; una regla recurrente no certifica que un estado esté conciliado.

Solo puede existir una regla por concepto/alias y cuenta. Para dos obligaciones del mismo comercio usa conceptos distintos y descriptores distinguibles. Pausar elimina las estimaciones futuras; cambiar el importe afecta todos los meses futuros estimados. Los movimientos reales permanecen intactos. No se admite todavía fecha final, periodicidad anual ni cambios de importe efectivos a partir de un mes posterior.

## Almacenamiento y respaldo

Las reglas se guardan en `.datos/recurrentes.sqlite3` dentro del repositorio de la Mac, excluido de Git. No están en Google Sheets ni en Railway. Para respaldarlas, detén el servicio y copia el archivo a un lugar privado; restáuralo en la misma ubicación antes de reiniciar. `RECURRENTES_DB` permite configurar otra ruta persistente.

## Validación

Desde el repositorio:

```bash
PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m unittest discover -s tests -v
```

Las pruebas usan datos ficticios y bases temporales. No llaman a Telegram ni a Google Sheets. Cubren reglas duplicadas, persistencia, pausa/reactivación, importes, alias, fechas, sustitución por cargos reales, filtros e integración con la proyección, además de las regresiones anteriores.
