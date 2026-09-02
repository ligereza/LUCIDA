# LUCIDA · Adobe

Migración local de la capa de exploración contextual y sus integraciones Adobe. El paquete mantiene separado el núcleo genérico, el companion flotante, los adaptadores host y el runtime histórico que necesita el bridge.

## Estructura

- `generic-interface-layer/`: núcleo independiente, contratos, seguridad, propuestas, acciones explícitas, auditoría, replay y providers opcionales.
- `companion/`: ventana flotante Electron y drag nativo de archivos.
- `adobe-context-shelf/photoshop-uxp/`: puente UXP para publicar contexto de Photoshop.
- `adapters/adobe/`: consumidores JSX/PSJS y contratos de Photoshop, Illustrator, Premiere y After Effects.
- `src/`: runtime histórico necesario por el servidor/bridge; no contiene proyectos ni assets de trabajo.
- `ICONOS/CHEMSEX/`: únicamente visuales propios/generated-by-Codex con asignación comprobable a láminas 1–8.
- `contracts/` y `src/tools/signal-bridge.mjs`: contrato de señales locales para XIO, VIZZ y PUPILA. Sólo acepta metadatos acotados; descarta contenido crudo y produce una superficie de propuestas, no acciones del host.
- `docs/legacy/`: capacidades, planes y documentación operativa migrada con identidad LUCIDA.

## Pruebas

```powershell
cd C:\IA\LUCIDA\adobe
npm test
npm run smoke
npm run companion:check
```

El núcleo no requiere Adobe, Electron, CUDA, MobileCLIP ni una base de assets para probarse. No se incluyeron `node_modules`, caches, pesos, modelos, credenciales ni bases privadas.

## CHEMSEX

El inventario y la trazabilidad están en:

- `ICONOS/CHEMSEX/manifest.json`
- `ICONOS/CHEMSEX/review-pending.json`
- `docs/migration-report.md`

Las ocho carpetas numeradas son planas; no hay subcarpetas dentro de `1`–`8`. Los originales de `C:\IA\svg` no se modificaron.

## Capa conectiva

El bridge local expone `POST /signals`, `GET /signals/current` y `GET /surface/current`. XIO puede publicar estado de red, aplicacion o workflow; VIZZ puede publicar estado de atencion y propuestas visuales; PUPILA puede publicar contexto de colaboracion o aprendizaje. La companion muestra los tres estados y usa sus metadatos para refinar recomendaciones.

El contrato es deliberadamente pequeno: no reenvia texto, rutas, imagenes, archivos, teclas, comandos, scripts ni URLs. Las propuestas de VIZZ/PUPILA son siempre reversibles cuando es posible, requieren confirmacion y permanecen `proposalOnly`; ningun evento externo ejecuta una accion en Photoshop, Illustrator, Premiere o After Effects.
