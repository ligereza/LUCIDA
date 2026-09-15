# LUCIDA signal boundary

Esta capa recibe un envelope OSC/Resolume como dato inyectado. No abre sockets
ni descubre servicios: el transporte y el momento de llamar a `receive` son
responsabilidad del host.

## Contrato

`OscEnvelope` valida:

- `address`: ruta OSC ASCII dentro de `/lucida/instar`, `/lucida/nayade`,
  `/lucida/imago` o `/composition`;
- `arguments`: escalares JSON seguros y ASCII cuando son texto;
- `timestamp`: ISO-8601;
- `sequence`: entero no negativo y estrictamente creciente;
- `source`: identificador ASCII estable.

El envelope se normaliza a `VJEvent` y entra al mismo `LucidaOrchestrator` que
los demás eventos. El resultado devuelve una única superficie con estado,
propuestas, resultados registrados y límites conocidos.

## Sender opcional

Un `sender` puede inyectarse explícitamente para publicar un aviso en
`/lucida/proposal`. Ese mensaje sólo notifica propuestas pendientes; no es una
orden de Resolume y LUCIDA no tiene un método de ejecución automática.

Sin sender, el mensaje se devuelve en el resultado con `sender_called=false`.
Esto permite usar el boundary en tests, replay y hosts que quieran decidir por
separado cómo transportar la notificación.

## Consumer XIO

`xio_bridge.py` consume un `ApplicationEvent` canónico con todos sus campos de
identidad, reloj, secuencia, hash y provenance. Valida el schema, exige clocks
con timezone y convierte el evento a `VJEvent` + `SignalEnvelope` para
`SessionReplay`. El evento original queda en `payload.xio_provenance` y en el
audit metadata.

El consumidor sólo acepta un dict o un objeto ya validado. No abre sockets, no
necesita Resolume y no ejecuta acciones. `XioEventConsumer.read_overlay()` y
`read_overlay_cursor()` exponen la misma vista acotada y cursor de revisión de
LUCIDA sin copiar payload ni provenance de XIO al overlay.
El resultado serializable está descrito por
[`xio-consume-result.schema.json`](contracts/xio-consume-result.schema.json),
que referencia el contrato común de `overlay_update`.
`validate_xio_consume_result()` permite validar ese resultado en runtime antes
de aceptarlo, comprobando también la identidad y secuencia entre XIO, replay,
signal y overlay.
Las referencias del grafo XIO usan los `$id` URN de cada contrato; un host que
use JSON Schema debe registrarlos localmente y no depender de resolver rutas o
descargar schemas durante un show.

## Signal profile

`profile.py` normaliza el contrato compartido de señal para `INSTAR`, `NAYADE`
e `IMAGO`. Conserva cada dato como `declared`, `observed`, `inferred` o
`unknown`, junto con su confianza y fuente. `validate_signal_profile()` sólo
valida y devuelve una copia canónica; no identifica módulos, no infiere un
procesador desde HDMI y no escribe en hardware.

`unknown` tiene una representación explícita y no ambigua: `value` debe ser
`"unknown"` y `confidence` debe ser `0`. Un dato concreto con confianza baja
no es `unknown`; debe conservar su origen real (`declared`, `observed` o
`inferred`) para que NAYADE pueda distinguir ausencia de información de una
medición débil. `inferred` puede omitir `source` cuando la hipótesis proviene
del cálculo local del adaptador; si existe una fuente, se conserva.
`summarize_signal_profile()` expone a NAYADE únicamente métricas acotadas para
el overlay: validez, etapa, conteos de desconocidos/inferidos, confianza mínima
y modo read-only del procesador.
`compare_signal_profiles()` permite contrastar un baseline con una observación y
reporta sólo drift, cambios de origen y procedencia, capacidades del procesador,
caídas de confianza y deltas de datos desconocidos; nunca devuelve los valores
crudos.
La misma proyección acotada se conserva cuando el flujo pasa de NAYADE a IMAGO,
por lo que una deriva observada durante el show sigue siendo visible sin
convertirse en una corrección automática.
Cuando existe drift, las propuestas de ambas etapas lo indican mediante un
conteo acotado y la evidencia `profile-drift`; no incluyen los valores que
cambiaron.
El conteo incluye diferencias de hechos, origen, confianza, recomendación,
modo read-only y etapa; el overlay sólo expone el total y banderas booleanas.
El estado de sesión puede heredar esas métricas acotadas hacia IMAGO cuando un
evento de show no repite el perfil; esa herencia se marca como `inherited` y no
se considera una nueva medición.
La propuesta también distingue esa herencia en su razón y evidencia para no
presentar un dato antiguo como una observación del show actual.
Al restaurar una sesión, la clave interna se somete a una allowlist de tipos y
valores; el contexto inválido se elimina antes de volver a proyectarse.

El schema de referencia es
[`signal-profile.schema.json`](../../schemas/signal-profile.schema.json).

## Host result receipt

Una propuesta puede recibir un `ProposalDecision` con estado `accepted`,
`rejected` o `unknown`. La confirmación explícita es obligatoria para los dos
primeros estados y está prohibida para `unknown`. El `HostResult` conserva
estado, razón, secuencia, timestamp, fuente, provenance, ids relacionados y
el overlay de solo lectura. Puede reconstruirse desde `to_dict()` mediante
`HostResult.from_dict()` para validar un receipt recibido o reproducido.

El `HostResult` es evidencia de recepción y decisión del host, no evidencia de
ejecución. No prueba que Resolume o un procesador haya ejecutado algo y su modo
válido es `proposal_only`. `ProposalDecisionRecorder` puede recibir un sink
inyectado —por ejemplo `SessionReplay.record_audit`— para anexar el receipt al
audit log sin mutar `VJProposal` ni convertirlo en una acción.

`HostSignalBoundary.public_report()` y `XioEventConsumer.public_report()` exponen
el mismo reporte público acotado de `SessionReplay`. Ambos eliminan payloads,
argumentos de señal, metadata y provenance antes de compartir la sesión; los
campos técnicos adicionales que aparecen en los reportes internos de XIO no se
propagan al contrato público.

Por diseño, `HostResult.to_dict()` y `XioConsumeResult.to_dict()` son contratos
de integración internos: conservan provenance o payload para correlación y
diagnóstico. No deben usarse como exportación pública; para eso se debe llamar
`public_report()` en el boundary o consumer correspondiente.

## Errores de frontera

- `EnvelopeValidationError`: envelope o argumento inválido.
- `UnknownAddressError`: address fuera de la frontera conocida.
- `SequenceOrderError`: secuencia atrasada.
- `DuplicateEnvelopeError`: secuencia ya recibida.
- `OutgoingSenderError`: falló un sender proporcionado explícitamente.

## Pendiente para un plugin nativo de Resolume

Esta capa no sustituye un plugin FFGL ni una integración autorizada con el SDK
de Resolume. Todavía se debe resolver, fuera de este boundary:

- el mecanismo oficial de transporte y sus permisos;
- el ciclo de vida del plugin nativo y compatibilidad por versión;
- lectura real de clips, cues, composición y output;
- manejo de hilos, latencia y backpressure del host;
- empaquetado, firma, instalación y rollback.

La frontera recomendada sigue siendo `host -> injected envelope -> VJEvent ->
LUCIDA -> proposal -> explicit result`.
