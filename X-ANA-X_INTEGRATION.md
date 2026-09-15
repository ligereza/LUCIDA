# Integración de LUCIDA con X-ANA-X

La implementación canónica está en `https://github.com/ligereza/X-ANA-X`,
rama `LUCIDA`. `X-ANA-X` conserva el motor compartido; este repositorio
independiente conserva las ramas de trabajo de host.

| Rama LUCIDA | Destino canónico | Responsabilidad |
|---|---|---|
| `ADOBE` | `LUCIDA/adobe/` | Companion local y adaptadores Adobe. |
| `RESOLUME` | `LUCIDA/lucida/`, `LUCIDA/adapters/vj/`, `LUCIDA/resolume/` | Replay, propuesta y herramientas de show/venue. |
| `MULTI` | `LUCIDA/multi/` | Frontera futura de sesiones; no activa por sí sola transporte. |

El paquete de preflight y herramientas específicas de show vive en
`resolume/adapter/` y se refleja en `LUCIDA/resolume/adapter/`. El código
compartido nuevo se modifica en el motor canónico; una mejora de host se
desarrolla en su rama de superficie y se porta con su commit de origen.

## Límites de integración

- Las ramas de host no se fusionan entre sí.
- Replay, fixtures y propuestas no prueban uso de Resolume, GPU, cámara, red,
  hardware ni timing de venue.
- Las propuestas siguen siendo `proposal_only`; ninguna prueba de esta rama
  abre Resolume ni ejecuta acciones del host.
- No se incluyen work ledgers, caches, assets privados ni resultados locales.

## Validación offline

```text
python -B -m pytest -q -o addopts= tests
python -B -m lucida.signals.smoke
python -B -m pytest -q -o addopts= resolume/adapter/tests resolume/adapter/tools/tests
```
