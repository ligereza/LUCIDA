# LUCIDA/RESOLUME — mapa de trabajo para agentes

Este documento corresponde a la rama `RESOLUME` del repositorio LUCIDA.
Describe dónde vive cada capa y qué documentación representa el estado
actual del código, no una colección de ramas auxiliares.

## Arquitectura de la rama

- `lucida/`: motor común, contratos, replay, señales y proyección.
- `resolume/`: superficie Resolume, replay y evidencia.
- `resolume/adapter/`: herramientas operativas de INSTAR, NAYADE e IMAGO.
- `tests/`: pruebas de la superficie común y sus conectores.

Las ramas permanentes del repositorio son `main`, `ADOBE`, `RESOLUME`
y `MULTI`. En esta rama, el trabajo específico de Resolume se concentra
en `resolume/` y `resolume/adapter/`; las mejoras compartidas pertenecen
al motor `lucida/`.

## Lectura de trabajo

1. Para el motor común: `lucida/README.md`, `lucida/engine/README.md` y
   `lucida/engine/INTEGRATION.md`.
2. Para la frontera de señales: `lucida/signals/README.md` y los módulos
   de `lucida/signals/`.
3. Para Resolume: `resolume/README.md`, este directorio y sus contratos.
4. Para la herramienta operativa: `resolume/adapter/README.md` y
   `resolume/adapter/CAPACIDADES.md`.

## Validación

Los recorridos reproducibles se ejecutan desde la raíz del repositorio:

`python -B -m pytest -q -o addopts= tests`
`python -B -m lucida.signals.smoke`
`python -B -m pytest -q -o addopts= resolume/adapter/tests resolume/adapter/tools/tests`

Los manifests de `resolume/` conservan la procedencia de sus ejecuciones
históricas. Sus commits candidato, hashes y conteos no sustituyen el estado
del HEAD actual.

Las referencias antiguas a ramas `agent/*` y al repositorio
`ligereza/resolume_adapter` corresponden a documentación heredada y no
son ramas activas de LUCIDA. El identificador técnico `resolume_adapter`
se mantiene únicamente en nombres de módulos, CLI y fixtures por
compatibilidad.
