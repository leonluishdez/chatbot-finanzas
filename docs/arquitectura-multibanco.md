# Arquitectura multibanco propuesta

La conciliación, la detección de duplicados y el registro actuales se mantienen como un motor común. Cada banco sólo aporta un adaptador de lectura de PDF que normaliza su información antes de entregarla a ese motor.

```text
PDF del banco
  -> adaptador específico
  -> EstadoNormalizado + MovimientoNormalizado
  -> validación común
  -> conciliación y duplicados
  -> simulación / registro en Sheets
```

## Contrato normalizado

Un adaptador debe producir el nombre de cuenta, periodo, fecha de corte, fecha límite, pago requerido, cargos, abonos y cuotas/MSI. Cada movimiento incluye fecha de compra cuando exista, descripción original, monto, tipo (`cargo`, `abono` o `cuota`) y los datos de parcialidad cuando se conozcan.

## Incorporar un banco nuevo

1. Crear un adaptador que reconozca y extraiga únicamente su formato de PDF.
2. Probar el adaptador con estados anonimizados de ese banco.
3. Pasar su salida al motor actual en modo simulación.
4. Validar estado, conciliación e idempotencia antes de permitir `--aplicar`.

Las diferencias contables que dependan de cada emisor, como qué abonos forman parte del pago requerido, quedan declaradas en el adaptador. El motor común no debe acumular condiciones `if banco == ...`.
