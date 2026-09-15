# LUCIDA / RESOLUME

Esta rama contiene la superficie de LUCIDA para flujos VJ y Resolume. LUCIDA
propone, registra y proyecta; no envía comandos a Resolume ni modifica un
showfile o un procesador sin una política y autorización explícitas.

## Integración canónica

El motor común vive en `X-ANA-X/LUCIDA/lucida/`. Esta copia de trabajo se
sincronizó desde `ligereza/X-ANA-X`, rama `LUCIDA`, commit
`44b456d`.

- `lucida/`: contratos, eventos, replay y proyección compartidos.
- `adapters/vj/`: adaptación de eventos y propuestas del flujo VJ.
- `resolume/`: replay y evidencia offline de la superficie Resolume.
- `resolume/adapter/`: herramientas especializadas de preflight, análisis de
  medios, fixtures, esquemas y runbooks para show/venue, portadas desde
  `X-ANA-X/LUCIDA/resolume/adapter/`.

El paquete `resolume/adapter/` conserva su protocolo de overlay y pruebas
específicas del dominio. La lógica nueva compartida pertenece a `lucida/` y a
la rama canónica de X-ANA-X; no se debe crear otro motor común dentro del
adaptador.

## Validación offline

Desde la raíz de este repositorio:

```powershell
python -B -m pytest -q -o addopts=
python -B -m lucida.signals.smoke
```

Para validar las herramientas específicas de show:

```powershell
python -B -m pytest -q -o addopts= resolume/adapter/tests resolume/adapter/tools/tests
```

Estas pruebas no abren Resolume, cámaras, sockets, GPU ni hardware. Un replay
`REVIEW` y una propuesta pendiente no equivalen a validación en venue.
