# Nota de evidencia para Obras Experimentales 2027

## Alcance y procedencia

`[VERIFIED]` Esta nota resume evidencia tecnica offline ya registrada en
`resolume/postulation-handoff.json`. No agrega resultados de instalacion,
venue, hardware o ejecucion live.

`[VERIFIED]` El handoff tiene SHA-256 canonico `23c9f12f44c60f8d9bb71b0837106681e024153911b1821d042eab07f1176540`.
El hash usa la misma normalizacion CRLF a LF que el evidence bundle.

`[VERIFIED]` La procedencia de commits registrada en el handoff es:

| Campo | Valor | Significado |
|---|---|---|
| `base_commit` | `e2f2cb15a51b0b82be72973de40e96f40675ab23` | Base RESOLUME limpia |
| `candidate_commit` | `a155762d946cff2cf41f2cc68c721ad77f3b4445` | Candidato fast-forwardable |
| `candidate_parent_commit` | `7722ce7ae5c619c63e7587b8f08854bb403fed4a` | Padre del candidato |
| `rehearsal_commit` | `ef6262a7d408db873dc8f25e969253a954cf95bb` | Ensayo desde base RESOLUME |
| `runtime_integration_base_commit` | `ac0fb16734483f48517696c2a1d3619d72a5df84` | Base historica del runtime offline |
| `current_handoff_snapshot_commit` | `ef6262a7d408db873dc8f25e969253a954cf95bb` | Commit usado para el snapshot de evidencia |

`[VERIFIED]` El bundle generado despues del handoff identifica el
`artifact_source_commit` como el `HEAD` local exacto usado para generarlo.
Ese campo no debe confundirse con `runtime_integration_base_commit` ni con
`candidate_commit`.

## Mapeo de evidencia a propuesta

| claim | evidence | status | limit |
|---|---|---|---|
| `mathematical_layout` como eje declarado | `semantic tape` determinista con `tape_schema`, `tape_sha256`, `frame_count` y proposal evidence; `SurfaceProjectionV1` conserva identidad y evidencia | `PROSPECTIVE` | No demuestra physical layout reconstruction, camera calibration, photometry, venue phase measurement, mapping accuracy ni fixture accuracy |
| `software_feasibility` | `signal-envelope-v1` validado; replay hacia semantic proposal, `SurfaceProjectionV1`, read-only overlay y evidence bundle | `VERIFIED` | La prueba es offline; no demuestra live protocol, host execution, multi-device backend ni venue timing |
| `deterministic_replay` | `replay_signal_envelope_v1_fixture` y smoke estable; `freeze_snapshot_tests_passed=121` | `VERIFIED` | La determinacion aplica a los fixtures registrados, no a una entrada live no registrada |
| `proposal_only` | `execution_mode=proposal_only`, `automatic_actions=false`, `external_side_effects=false` | `VERIFIED` | No autoriza ni prueba una ejecucion live |
| `explicit_approval` | `requires_explicit_approval=true` y `overlay_status=pending_approval` | `VERIFIED` | La aprobacion de un operador en venue queda fuera del ensayo |
| `reversible_projection` | `reversible=true` en la proposal y en la projection; estado `pending_approval` | `VERIFIED` | No se probaron rollback operativo, patch recovery ni recuperacion de un host live |
| `Resolume`, `audio`, `lighting`, `venue` y `hardware` | El handoff registra `live_resolume=false`, `live_audio=false`, `live_hardware=false` y ausencia de network, GPU, camera y transport | `PROSPECTIVE` | No existe validacion de live Resolume, audio sync, luces, venue, hardware, calibration, timing, network, GPU o camera |

`[VERIFIED]` La tabla distingue el soporte tecnico del candidato de las
afirmaciones que deben permanecer prospectivas en la propuesta. En particular,
`mathematical_layout` se presenta como un eje declarado y preparatorio, no como
un resultado fisico ya obtenido.

## Matriz machine-readable para el package manifest

`[VERIFIED]` La matriz determinista
`resolume/postulation-evidence-matrix.json` convierte cada claim en un registro
con `claim_id`, `evidence_refs`, `status`, `allowed_use`, `limit` y
`verification_command`. Su referencia al handoff usa el SHA-256
`23c9f12f44c60f8d9bb71b0837106681e024153911b1821d042eab07f1176540`.

`[VERIFIED]` La matriz conserva la separacion entre `VERIFIED`, `PROSPECTIVE` y
`OPERATOR_DEPENDENT`. Sus registros no contienen frames, source code, media ni
otra copia del replay.

`[OPERATOR_DEPENDENT]` El package manifest de Obras puede consumir esta matriz
como metadata interna para seleccionar claims permitidos y sus limites, sin
convertirla en un attachment ni presentarla como una observacion independiente
de venue.

## Frontera de software comprobada

`[VERIFIED]` El camino offline comprobado es:

```text
lucida.replay.session.replay_signal_envelope_v1_fixture
  -> lucida.signals.replay.replay_fixture
  -> lucida.signals.semantic_light_field.project_semantic_light_field_report
  -> lucida.surface_projection.SurfaceProjectionV1
  -> lucida.signals.boundary.OscResolumeBoundary
  -> lucida.evidence_bundle.build_evidence_bundle
```

`[VERIFIED]` El resultado registrado es `smoke_status=REVIEW`,
`proposal_id=proposal-cli-light-field-001`, `overlay_status=pending_approval`,
`execution_mode=proposal_only`, `requires_explicit_approval=true`,
`reversible=true` y `external_side_effects=false`.

`[VERIFIED]` `SurfaceProjectionV1` contiene solo los campos compartidos de
proposal, evidence, host identity, surface identity, approval, reversibility y
safety. `tape schema`, `tape hash`, `frame count`, `calibration status` y OSC
details permanecen fuera del shared projection, en la frontera RESOLUME.

`[VERIFIED]` El handoff registra `candidate_tests_passed=116`,
`rehearsal_tests_passed=118`, `freeze_snapshot_tests_passed=121` y
`freeze_snapshot_tests_failed=0`. Los hashes de evidencia son:

| Artifact | SHA-256 |
|---|---|
| `surface_projection_schema` | `3bca2f33944f062acfbb9aef6444e4b84d5977bb7eede7f31673d7360e7a356e` |
| `signal_envelope_fixture` | `0b806342e2d51dd6dce4bf330579aec6bf60b494c50bb2196357eee736c5023f` |
| `semantic_report_fixture` | `c0939a24b4b80850b30a351bc497323dad8dd7aaa7d9e8bfa57e6d64f1db2286` |
| `tape` | `f69e170a3447924a7e30126572c659bf61a353d6628ae9e4cd1359aa035bbaec` |

## Limite frente a una instalacion real

`[VERIFIED]` La evidencia demuestra una frontera de software reproducible,
proposal-only, reversible y sin side effects externos dentro del worktree
aislado.

`[PROSPECTIVE]` La propuesta puede describir una futura traduccion de estado
semantic hacia light y audio despues de una aprobacion y una validacion de
venue.

`[OPERATOR_DEPENDENT]` La integracion candidata solo puede avanzar mediante el
comando documentado en el handoff, desde un checkout limpio y despues de una
decision explicita del operador:

```text
git merge --ff-only a155762d946cff2cf41f2cc68c721ad77f3b4445
```

`[VERIFIED]` Ese comando no fue ejecutado en `C:\IA\LUCIDA`. El checkout
principal conserva su estado `RESOLUME` y el path preexistente `adobe/` no fue
leido ni modificado.

## Naturaleza interna de este artefacto

`[VERIFIED]` Este archivo es evidencia interna del repositorio: apunta al
handoff, conserva sus commits y hashes, y traduce resultados de fixtures y
tests a limites de la propuesta. No es un attachment de instalacion ni una
observacion independiente de un venue.

`[OPERATOR_DEPENDENT]` Un evaluador puede reproducir la evidencia solo desde el full LUCIDA worktree,
que contiene `lucida/`, `tests/`, schemas, fixtures y
las dependencias Python. Desde ese worktree puede ejecutar
`python -m lucida.evidence_bundle --report`,
`python -m lucida.evidence_bundle --json` y los comandos de replay descritos en
el handoff.

`[VERIFIED]` El transfer artifact set descrito en
`resolume/postulation-integration-manifest.json` contiene solo tres artifacts
de evidencia. No contiene source modules, tests, schemas, fixtures ni runtime
dependencies; por tanto no es ejecutable por si solo y solo permite inspeccion
de JSON, hashes y texto.

`[PROSPECTIVE]` La reproduccion desde el full LUCIDA worktree confirma
software offline; no convierte en verificadas las partes live que el handoff
marca como prospectivas o no testeadas.
