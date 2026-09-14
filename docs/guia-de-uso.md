# Guía de uso — Chatbot Finanzas

El bot funciona en tu Mac y guarda los movimientos en Google Sheets. No necesitas abrir VS Code para usar Telegram. Para que responda y mande recordatorios, la Mac debe estar encendida, despierta y con internet.

## Uso diario en Telegram

### Registrar un gasto

Escribe el gasto con importe y, si la sabes, cuenta:

```text
Registra gasto de tacos por $250 con Invex
Registra compra de vuelo por $11,049 con Invex a 6 meses
```

El bot pide la cuenta si falta, muestra categorías para elegir y después presenta un resumen para confirmar. Un gasto de contado queda `Pendiente`; un gasto a meses crea una fila por cada mensualidad.

Las cuentas de gasto disponibles son `BBVA Platinum`, `Citibanamex Oro`, `Citibanamex Costco` e `Invex`. Las categorías de gasto son Comida, Transporte, Servicios, Entretenimiento, Viajes, Salud, Aprendizaje, PPR, Amazon y Varios.

### Registrar un ingreso

```text
Recibí $25,000 de sueldo
Registra ingreso de comisión por $3,500
```

El bot registra los ingresos como `Pagado` en `BBVA Debito`. Sirven para calcular el promedio de ingresos de la proyección financiera.

### Consultas normales

Ejemplos útiles:

```text
¿Cuánto gasté este mes?
¿Cuánto gasté en viajes?
¿Cuánto tengo pendiente con Invex?
¿Cuánto tengo pendiente los próximos 6 meses?
Estado de Costco septiembre 2026
```

La consulta de los próximos meses muestra el promedio de los últimos tres meses completos de ingresos reales, los gastos pendientes y el disponible estimado de cada mes.

### Clasificar movimientos importados

```text
/clasificar
```

Muestra uno a uno los gastos importados que siguen como `Sin clasificar`. Elige una categoría con los botones. Úsalo después de importar un estado de cuenta.

## Gastos recurrentes

La manera sencilla es escribir:

```text
Registra un gasto recurrente de Totalplay por $460 al mes
```

El bot pregunta cuenta, categoría, día de pago y mes inicial. Confirma solo si el resumen es correcto. La regla entra en las proyecciones futuras, pero no crea movimientos bancarios en Sheets.

Comandos disponibles:

```text
/recurrentes
/recurrentes ayuda
/recurrentes pausar ID
/recurrentes activar ID
/recurrentes importe ID | nuevo importe
/recurrentes alias ID | descripción exacta del banco
```

`alias` sirve cuando el nombre del cargo bancario no coincide con el concepto que usaste para crear el recurrente. Consulta [Gastos recurrentes](recurrentes.md) para el detalle.

## Recordatorios de pago

```text
/recordatorios activar
/recordatorios probar
/recordatorios desactivar
```

Después de activarlos, a las 9:00 a.m. el bot avisa los gastos `Pendiente` que vencen al día siguiente. Cada vencimiento se avisa una sola vez. `probar` muestra qué aviso recibirías para mañana sin marcarlo como enviado. Consulta [Recordatorios de pago](recordatorios.md) para sus límites.

## Alta y conciliación de un nuevo estado de cuenta

Guarda el PDF dentro de la carpeta `estados/` del proyecto. Este es el flujo recomendado: primero simular, luego aplicar y finalmente comprobar que no intente duplicar nada.

Abre una terminal en el proyecto y ejecuta:

```bash
cd /Users/luisleon/workspace/chatbot-finanzas
source .venv/bin/activate
```

### 1. Simular: no modifica Google Sheets

```bash
python importar_estado.py "estados/Citibanamex Costco septiembre 2026.pdf"
```

Revisa antes de aplicar:

- Cuenta, periodo, fecha límite y pago para no generar intereses.
- Que aparezca `EL ESTADO CUADRA`.
- Las cifras de `Coincidencias`, `Solo banco` y `Solo Sheets`.
- Los cargos regulares o cuotas que propone agregar.

`Solo banco` significa que el PDF tiene un movimiento todavía ausente en Sheets. `Solo Sheets` significa que Sheets tiene un movimiento que no aparece en ese estado. No apliques a ciegas si hay una diferencia que no reconoces.

### 2. Revisar diferencias manuales, cuando hagan falta

Si la simulación muestra movimientos que requieren tu decisión, usa la revisión asistida primero sin modificar nada:

```bash
python revisar_estado.py "estados/Citibanamex Costco septiembre 2026.pdf"
```

Sigue las preguntas del programa. Cuando tus decisiones estén claras, repite con `--aplicar`:

```bash
python revisar_estado.py "estados/Citibanamex Costco septiembre 2026.pdf" --aplicar
```

### 3. Aplicar la importación validada

Si la simulación de `importar_estado.py` está correcta, guarda los movimientos propuestos:

```bash
python importar_estado.py "estados/Citibanamex Costco septiembre 2026.pdf" --aplicar
```

Esto registra el estado, sus cargos faltantes validados y las cuotas detectadas. No reescribas ni borres movimientos existentes durante este paso.

### 4. Cotejo final: volver a simular

Ejecuta de nuevo el mismo comando sin `--aplicar`:

```bash
python importar_estado.py "estados/Citibanamex Costco septiembre 2026.pdf"
```

El objetivo es que no proponga cargos ni cuotas nuevos. Lo ideal es `Solo banco: 0` y, si no existen movimientos esperados registrados por adelantado, `Solo Sheets: 0`. Después usa `/clasificar` en Telegram para categorizar los nuevos gastos.

### Alta manual de un estado, sin PDF

Solo cuando ya tienes los movimientos registrados y quieres guardar el resumen del banco, puedes escribir en Telegram:

```text
Registra estado de Costco septiembre 2026 pago para no generar intereses $15,819.67
```

El bot calcula el corte y la fecha límite de la tarjeta, compara el total capturado con el importe del banco y guarda el estado como `Conciliado` o `Revisar`. Esto no extrae ni da de alta los movimientos individuales del PDF; para eso usa el flujo de importación anterior.

## Fechas y seguridad de datos

Las fechas nuevas se muestran como `dd/m/yy`, por ejemplo `05/9/26`. El código se guarda en GitHub, pero `.env`, `service_account.json`, PDFs de `estados/` y las bases locales de recurrentes y recordatorios permanecen fuera de Git.
