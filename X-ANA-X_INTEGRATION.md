# Integración con X-ANA-X

## Fuente canónica

La integración canónica vive en:

https://github.com/ligereza/X-ANA-X/tree/LUCIDA

LUCIDA es la capa transparente de integración con aplicaciones. Mantiene la
separación entre el motor común, la representación y el adaptador de cada
host.

## Mapa de ramas de este repositorio

| Rama | Responsabilidad | Destino en X-ANA-X/LUCIDA |
|---|---|---|
| main | Base de LUCIDA | LUCIDA/ |
| ADOBE | Superficie y adaptación para Adobe | LUCIDA/adapters/ y señales Adobe |
| RESOLUME | Integración VJ y Resolume | LUCIDA/resolume/ y LUCIDA/resolume/adapter |
| MULTI | Frontera multiusuario futura | LUCIDA/multi/ |
| codex/adobe-adaptive-composition | Composición para Adobe | LUCIDA/adapters/ y señales Adobe |
| codex/lucida-python-engine | Motor Python de la capa | LUCIDA/lucida/ |
| codex/lucida-resolume-final-merge-gate | Gate de merge de Resolume | LUCIDA/resolume/adapter |
| codex/lucida-resolume-freeze | Congelamiento de Resolume | LUCIDA/resolume/adapter |
| codex/lucida-resolume-overlay | Overlay de Resolume | LUCIDA/resolume/adapter |
| codex/lucida-resolume-rc-rehearsal | Ensayo de release candidate | LUCIDA/resolume/adapter |
| codex/lucida-resolume-runtime | Runtime de Resolume | LUCIDA/resolume/adapter |
| codex/lucida-resolume-semantic-light-field | Campo semántico de Resolume | LUCIDA/resolume/adapter |
| docs/next | Documentación y decisiones | documentación de LUCIDA |

El adaptador de Resolume no se trabaja como repositorio independiente: su
destino activo es LUCIDA/resolume/adapter dentro de X-ANA-X.

## Cómo portar trabajo

1. Mantener el cambio en la rama de host que le corresponde.
2. Probarlo sin abrir una aplicación real cuando el contrato sea de replay,
   preview o propuesta.
3. Portar el commit a X-ANA-X/LUCIDA en la ruta indicada.
4. No mover lógica común al adaptador si puede vivir en LUCIDA/lucida o en
   core; no mover lógica específica del host al núcleo.

La integración no afirma que una aplicación real, GPU, cámara, red o hardware
hayan sido probados si no existe evidencia de esa ejecución.

## Validación

En el adaptador integrado:

PYTHONPATH=tools:. python -m pytest -q -o addopts=

En las pruebas compartidas de X-ANA-X:

PYTHONPATH=LUCIDA python -m pytest -q -o addopts= LUCIDA/tests
