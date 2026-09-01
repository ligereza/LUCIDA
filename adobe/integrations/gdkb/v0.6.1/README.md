# GDKB 0.6.1 integrado

Este directorio conserva los cuatro artefactos entregados en
`GDKB_0_6_1_COMPLETE.zip` y sus manifiestos originales:

- `core/`: normalización y resolución conservadora.
- `import_engine/`: importación determinista de registros JSONL.
- `identity_evidence/`: identidad, observación, evidencia, assertion y lifecycle.
- `event_state/`: event log, reconstrucción, snapshots y diff.
- `gdkb-architecture.png`: diagrama incluido en el bundle.

El runtime que usa el toolkit está ensamblado en
`adapters/gdkb/runtime/gdkb/`. Reutiliza los módulos compatibles del bundle
con una sola normalización común; los cuatro árboles originales permanecen
intactos para auditoría y comparación.

## Integración con Agent Toolkit

El adaptador [bridge.py](../../../adapters/gdkb/bridge.py) expone un contrato
JSON sobre stdin/stdout. Las herramientas Node están en
`src/tools/gdkb.mjs` y aparecen en `registry.json`:

- `gdkb.health`
- `gdkb.normalize`
- `gdkb.resolve`
- `gdkb.import`
- `gdkb.replay`
- `gdkb.merge-event`

La búsqueda de iconografía (`asset.search`) usa esta capa para normalizar la
consulta y clasificar los resultados semánticos como `confirmed`, `candidate` o
`needs_review`. La similitud difusa nunca confirma una identidad por sí sola.

## SQL

Las migraciones se conservan separadas porque representan etapas distintas:

1. `core/sql/001_core.sql`: modelo inicial.
2. `import_engine/sql/002_import_tables.sql`: lotes y registros importados.
3. `identity_evidence/schemas/003_identity_evidence_lifecycle.sql`: modelo
   ampliado de observación, evidencia y lifecycle.
4. `event_state/schemas/004_event_log.sql`: historial de eventos y snapshots.

No se ejecutan automáticamente. Antes de conectar PostgreSQL hay que elegir la
variante de identidad canónica y convertirlas en una migración única ordenada.
Esto evita crear dos tablas `entity`/`source` incompatibles por accidente.

## Contrato de seguridad conceptual

- los valores originales se conservan;
- la normalización es derivada;
- una fuente no es una entidad;
- una assertion conserva evidencia;
- merge/split son eventos auditables y no borran historia;
- snapshots son vistas reproducibles, no la autoridad histórica.
