# LUCIDA

LUCIDA es la capa integradora de MOSAIK/VJ: una única superficie estructurada
que coordina tres capacidades internas —`INSTAR`, `NAYADE` e `IMAGO`— sin
convertirlas en tres interfaces separadas.

La primera entrega es deliberadamente offline y proposal-only. Consume los
contratos comunes de `adapters.vj` (`VJEvent`, `VJState`, `VJProposal` y
`VJResult`), produce reportes de observación y permite registrar resultados,
pero no abre Resolume, no accede a hardware y no ejecuta acciones.

## Flujo

```text
VJEvent + VJState
       |
       v
LUCIDA Orchestrator
       |
       +--> INSTAR  - preflight de medios y mapping
       +--> NAYADE  - soundcheck de señal y procesador
       +--> IMAGO   - show, incidente y recuperación
       |
       v
Single read-only overlay
       |
       +--> observaciones
       +--> estado por capacidad
       +--> propuestas explícitas
       +--> resultados esperados
       +--> desconocidos
```

## Uso mínimo

```python
from lucida import LucidaOrchestrator

orchestrator = LucidaOrchestrator()
state = orchestrator.initial_state("fictional-session")
state = orchestrator.propose(
    {
        "event_id": "evt-001",
        "timestamp": "2026-01-10T20:00:00Z",
        "phase": "preflight",
        "event_type": "phase.completed",
        "payload": {"status": "pass"},
    },
    state,
)
overlay = orchestrator.read_overlay(state)
```

`read_overlay` es una superficie de datos, no una ventana. Una futura UI puede
renderizarla dentro del host que corresponda, pero LUCIDA no asume un toolkit
gráfico ni una integración no autorizada.

## Replay y dry-run

```python
from lucida.replay import replay_path

report = replay_path("lucida/replay/fixtures/session-fictional.json")
assert report["status"] == "PASS"
```

El replay usa sólo el fixture ficticio, reloj incluido en los eventos y la
lógica pura del adaptador. Repetirlo con el mismo fixture produce el mismo
reporte.

## Límites y dependencias

- Dependencia de runtime: biblioteca estándar de Python y `adapters.vj`.
- `pytest` se usa únicamente para la suite de tests.
- No hay subprocess, red, GPU, Resolume, FFGL, DXV, DMX, Art-Net, sACN ni
  control de procesadores LED.
- Las propuestas requieren que un operador o un host autorizado decida qué
  hacer y registre el resultado; no existe un método de ejecución automática.
- Los detalles de medios, cues, mapping, GPU, protocolos y hardware siguen
  siendo implementaciones exclusivas o pendientes de MOSAIK.

La convención de ASCII técnico y la verificación offline están documentadas en
[`CONTRIBUTING.md`](CONTRIBUTING.md).

La frontera opcional de señales OSC/Resolume está documentada en
[`signals/README.md`](signals/README.md); recibe envelopes inyectados y no abre
sockets por sí misma.

## Siguiente integración con XIO

El siguiente paso es acordar un contrato de entrada con XIO para convertir su
registro de sesión en `VJEvent` sin copiar su almacenamiento ni introducir una
dependencia obligatoria. Después se puede añadir un adaptador de lectura que
alimente la superficie LUCIDA y mantenga la misma frontera proposal-only.
