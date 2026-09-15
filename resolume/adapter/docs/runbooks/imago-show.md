# IMAGO: show observation

IMAGO registra lo que ocurre durante el show sin convertirse en un control
remoto. Mantiene una secuencia de eventos para inicio, cues, incidentes,
recovery y cierre. Los eventos que requieren atencion generan propuestas
explicitas, reversibles y `proposal_only`.

## Crear una sesion

```powershell
python tools/resolume_adapter_cli.py imago-session init `
  --output .\artifacts\imago-session.json `
  --session-id show-01-imago
```

## Registrar observaciones

```powershell
python tools/resolume_adapter_cli.py imago-session event `
  .\artifacts\imago-session.json `
  --event-type show_started `
  --recorded-at 2026-01-10T22:00:00Z

python tools/resolume_adapter_cli.py imago-session event `
  .\artifacts\imago-session.json `
  --event-type incident_detected `
  --payload '{"category":"signal_review","reason":"Near black is lifted"}' `
  --recorded-at 2026-01-10T22:15:00Z
```

IMAGO no abre Resolume, no dispara cues, no escribe en procesadores y no manda
DMX. El resultado del operador se registra por separado para conservar la
diferencia entre observacion, propuesta y accion real.

## Ventana de resguardo

Durante un show se puede registrar una intención de probar un efecto o absorber
un missclick sin perder la visual base:

```powershell
python tools/resolume_adapter_cli.py imago-session event `
  .\artifacts\imago-session.json `
  --event-type guard_window_requested `
  --payload '{"duration_ms":5000,"base_clip_id":"clip-base-01","test_scope":"effect"}'
```

Esto crea la propuesta `prepare_guard_window`, que exige aprobación explícita y
queda limitada a un máximo de 60 segundos. La sesión registra la ventana como
intención auditable; no crea una capa, no congela un clip y no envía órdenes a
Resolume.
