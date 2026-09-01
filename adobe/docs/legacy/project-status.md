# Agent Toolkit — estado verificable

Este documento es una auditoría breve del objetivo original. `verified` significa
que existe evidencia local reproducible; `partial` significa que el contrato o
adaptador existe pero falta una prueba de runtime; `pending-external` depende de
un host, instalación o túnel que no está disponible en este equipo.

## Resumen

| Resultado | Estado |
|---|---|
| Estructura, jobs, herramientas SVG y orquestador | `verified` |
| Inventario de fuentes y mapa de scripting multi-aplicación | `verified` |
| Wrappers locales de three.js, stdlib, RxJS y Effect | `verified` |
| Blender 4.5.4 LTS, Geometry Nodes, SVG/PNG assets, GLB y render Cycles | `verified` |
| Illustrator 2026 | `verified` por JSX/COM |
| Photoshop 2026 | `verified` por JSX/COM; UXP directo `partial` |
| After Effects 2026 | `pending-external` por decisión del usuario |
| Premiere Pro | `pending-external`; instalación sin ejecutable |
| Puente web local | `verified` con token y CORS |
| Arena remoto | `pending-external`; requiere relay/túnel autenticado |
| Capa GDKB 0.6.1 | `verified` por bridge Python, fixtures y replay local |

## Auditoría de los 12 requisitos

1. **Aplicaciones Adobe exactas — `verified`**

   Las rutas configuradas están en `config.local.json` para Photoshop 2026,
   Illustrator 2026, After Effects 2026 y el Premiere detectado. Los
   ejecutables presentes se comprueban con `npm run verify`.

2. **Flujos prioritarios — `verified`**

   Están definidos en [CAPABILITIES.md](CAPABILITIES.md): imagen → SVG →
   animación → preview, imagen → Blender → render, imagen → Blender →
   Illustrator, datos → gráfico animado, búsqueda semántica → iconografía y
   SVG → host Adobe.

3. **Estructura `agent-toolkit` — `verified`**

   Existen `tools/`, `skills/`, `adapters/`, `templates/`, `jobs/`, `memory/`,
   `scripts/`, `src/`, `tests/` y `logs/`.

4. **Registro de capacidades — `verified`**

   [registry.json](registry.json) contiene 47 capacidades con estado,
   entrypoint, entradas y salidas. [CAPABILITIES.md](CAPABILITIES.md) contiene
   las reglas de selección y los pendientes.

   El inventario operativo vive en
   [`integrations/tool-sources.json`](integrations/tool-sources.json), el mapa de
   contratos en [`integrations/scripting-map.json`](integrations/scripting-map.json)
   y `integration.validate` comprueba ambos sin enumerar repositorios completos.

5. **Herramientas SVG — `verified`**

   `src/tools/svg.mjs` cubre creación, embedding, animación, partículas,
   validación y preview. `src/tools/vectorize.mjs` y
   `adapters/image/vectorize.py` cubren raster → paths. La validación incluye
   namespace, cierre XML, recursos embebidos y metadatos de accesibilidad.

6. **Sistema de trabajos — `verified`**

   Cada job mantiene `request.json`, `input/`, `work/`, `output/`,
   `status.json` y `summary.md`. Las entradas del workflow se copian a
   `input/` y las acciones se auditan en `logs/audit.ndjson`.

7. **Orquestador local — `verified`**

   `src/orchestrator.mjs` ejecuta el workflow principal; `src/dispatcher.mjs`
   selecciona herramientas allowlisted para CLI/API; `src/cli.mjs` ofrece la
   interfaz local. GDKB 0.6.1 se ejecuta mediante `adapters/gdkb/bridge.py` y
   alimenta la revisión semántica de `asset.search`.

8. **Blender — `verified`**

   `src/adapters/blender.mjs` y `adapters/blender/agent_blender.py` cubren
   creación de escenas, render, importación SVG, importación GLB y exportación
   GLB. Blender 4.5.4 LTS produjo `.blend` y previews PNG en Cycles en pruebas
   reales.

9. **Adobe — `partial` por host**

   Los envelopes viven en `jobs/<id>/adobe/commands/` y los resultados en
   `jobs/<id>/adobe/results/`.

   - Illustrator: importación SVG real completada por JSX/COM.
   - Photoshop: importación/exportación PNG real completada por JSX/COM;
     UXP `.psjs` preparado pero no ejecutado directamente desde el host.
   - After Effects: consumidores JSX y `aerender` preparados; runtime diferido.
   - Premiere: consumidor preparado; no hay ejecutable local para probarlo.

10. **Agente web — `verified` local / `pending-external` remoto**

    `src/server.mjs` expone `/agent-card`, `/capabilities`, `/openapi.json`,
    `/run`, jobs y Adobe. `/run` usa `src/dispatcher.mjs`, crea jobs aislados
    y no ejecuta shell arbitrario. After Effects permanece fuera del allowlist
    web hasta validar su host. El acceso desde Arena requiere un relay o túnel
    autenticado que todavía no está configurado.

11. **Seguridad — `verified` local**

    Hay allowlists de comandos y rutas, token Bearer, CORS explícito, límite de
    2 MB por petición, confirmación separada para sobrescritura, auditoría,
    validación de IDs y aislamiento de jobs. El servidor rechaza bindings no
    locales sin token.

12. **Flujo completo — `verified`**

    Se verificaron flujos reales imagen → SVG animado → preview → Blender,
    imagen → SVG animado → preview → Illustrator y la receta combinada
    imagen → SVG → Blender → Illustrator. También se verificaron normalización,
    importación fixture, resolución conservadora, merge con evidencia y
    reconstrucción de estado/snapshot de GDKB. Un job Adobe permanece en
    `waiting-for-adobe` hasta que `adobeStatus` encuentra su result envelope.

## Comandos de verificación

```powershell
cd C:\IA\LUCIDA\adobe
npm test
npm run verify
.\scripts\adobe-host-check.ps1
```

Los dos primeros comandos son deterministas y no requieren abrir Adobe.
