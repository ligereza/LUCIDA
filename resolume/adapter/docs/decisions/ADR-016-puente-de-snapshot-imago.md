# ADR-016: Puente seguro de snapshot IMAGO al contrato VJ

## Estado

Aceptado.

## Contexto

IMAGO mantiene el estado del show, checkpoints, incidentes, propuestas,
resultados y eventos observados. Ese estado no entraba al contrato comun del
adaptador VJ. Copiar los payloads completos o las notas de operador no es
necesario para un cursor de estado y puede propagar datos privados.

## Decision

`adapters/vj/imago_input.py` convierte un snapshot IMAGO en un evento cuya fase
se deriva del estado actual: `prepared` a `preparation`, `showing` a `show`,
`incident` a `incident`, `recovering` a `recovery` y `closed` a `closure`.

El payload conserva identificadores estables, contadores, tipos de eventos,
estados posteriores, checkpoint, resumen del perfil y operaciones de
propuestas. No copia payloads de eventos, notas, razones, rutas ni campos
desconocidos. Las propuestas deben mantener los invariantes
`requires_explicit_approval=true`, `reversible=true` y
`execution_mode=proposal_only`.

El productor proporciona `event_id` y `sequence`; `updated_at` debe incluir
zona horaria. El puente exige `read_only=true` y `commands_sent=false`.

## Consecuencias

- Un snapshot IMAGO puede alimentar el estado VJ y el replay sin importar la
  implementacion concreta de IMAGO.
- El resumen muestra que existe una propuesta o incidente, pero no sustituye
  la evidencia detallada conservada por IMAGO.
- Los cambios de fase siguen siendo validados por el contrato comun y no se
  convierten en acciones automáticas.
- Los eventos observacionales sin tipo de ciclo conocido derivan su status de
  la fase, para que un snapshot de cierre no quede como `active`.
- No se ejecutan cues, Resolume, DMX, sockets ni comandos de procesadores.

## Alternativas descartadas

- Copiar eventos completos: expone texto y payloads que no necesita el cursor.
- Ejecutar propuestas al construir el evento: elimina la aprobacion explicita
  y hace la recuperacion menos auditable.
- Inferir la fase desde el ultimo tipo de evento sin validar `status`: puede
  ocultar un snapshot inconsistente.
