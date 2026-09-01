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
necesita Resolume y no ejecuta acciones.

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
