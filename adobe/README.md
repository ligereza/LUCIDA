# LUCIDA · Adobe

Migración local de la capa de exploración contextual y sus integraciones Adobe. El paquete mantiene separado el núcleo genérico, el companion flotante, los adaptadores host y el runtime histórico que necesita el bridge.

## Estructura

- `generic-interface-layer/`: núcleo independiente, contratos, seguridad, propuestas, acciones explícitas, auditoría, replay y providers opcionales.
- `companion/`: ventana flotante Electron y drag nativo de archivos.
- `adobe-context-shelf/photoshop-uxp/`: puente UXP para publicar contexto de Photoshop.
- `adapters/adobe/`: consumidores JSX/PSJS y contratos de Photoshop, Illustrator, Premiere y After Effects.
- `src/`: runtime histórico necesario por el servidor/bridge; no contiene proyectos ni assets de trabajo.
- `ICONOS/CHEMSEX/`: visuales propios/generated-by-Codex, separados entre láminas 1–8 y la colección reutilizable `mini-icons`.
- La migración combina las salidas de `projects/chemsex` con los archivos visuales directamente contenidos en `projects/recolectados/lamina-*`; deduplica por hash SHA-256 y no incorpora las subcarpetas técnicas.
- `contracts/` y `src/tools/signal-bridge.mjs`: contrato de señales locales para XIO, VIZZ y PUPILA. Sólo acepta metadatos acotados; descarta contenido crudo y produce una superficie de propuestas, no acciones del host.
- `contracts/host-capabilities.json`: matriz única de hosts, adaptadores, operaciones y estados de validación de esta rama.
- `src/tools/adapter-parity.mjs`: auditoría estática que compara las operaciones del contrato con los dispatches reales de cada `agent.jsx`/`agent.psjs`; `npm run verify` la ejecuta antes de aceptar la rama.
- `integrations/signal-publisher/`: cliente Python sin dependencias para que los tres proyectos publiquen señales sin conocer el runtime Adobe.
- `docs/legacy/`: capacidades, planes y documentación operativa migrada con identidad LUCIDA.

## Alcance de esta rama

`ADOBE` contiene la companion transparente, el contexto de Photoshop, el
catalogo local y los adaptadores de Photoshop, Illustrator, After Effects y
Premiere. XIO, VIZZ y PUPILA sólo entran como señales acotadas; este bridge no
controla Resolume, no transporta sesiones entre equipos y no migra proyectos
de otras fuentes.

## Pruebas

```powershell
cd .\adobe
npm test
npm run smoke
npm run companion:check
python -m unittest tests/test_signal_publisher.py
```

El núcleo no requiere Adobe, Electron, CUDA, MobileCLIP ni una base de assets para probarse. No se incluyeron `node_modules`, caches, pesos, modelos, credenciales ni bases privadas.

## CHEMSEX

El inventario y la trazabilidad están en:

- `ICONOS/CHEMSEX/manifest.json`
- `ICONOS/CHEMSEX/review-pending.json`
- `docs/migration-report.md`

La ejecución actual incorpora 511 archivos únicos: 0 en las láminas 1 y 2,
124 en la 3, 131 en la 4, 57 en la 5, 30 en la 6, 42 en la 7, 31 en la 8
y 96 en `mini-icons`.

Las ocho carpetas numeradas y `mini-icons` son planas; no hay subcarpetas
dentro de ellas. Los originales de `C:\IA\svg` no se modificaron.

## Capa conectiva

El bridge local expone `POST /signals`, `GET /signals/current` y `GET /surface/current`. XIO puede publicar estado de red, aplicacion o workflow; VIZZ puede publicar estado de atencion y propuestas visuales; PUPILA puede publicar contexto de colaboracion o aprendizaje. La companion muestra los tres estados y usa sus metadatos para refinar recomendaciones.

La matriz de capacidades es la fuente de verdad de alcance para el agent-card. Photoshop tiene un proveedor UXP preparado pero aún requiere validación dentro del host; los otros hosts conservan adaptadores explícitos sin inventar un proveedor de contexto. Resolume, transporte entre dispositivos y migración de proyectos permanecen fuera de esta rama.

El bridge externo es deliberadamente pequeno: no reenvia rutas, imagenes, archivos, teclas, comandos, scripts ni URLs, y las señales externas no transportan contenido crudo. El contexto local de Adobe puede incluir texto acotado de la capa seleccionada para producir recomendaciones; nunca conserva la ruta del archivo. Las propuestas de VIZZ/PUPILA son siempre reversibles cuando es posible, requieren confirmacion y permanecen `proposalOnly`; ningun evento externo ejecuta una accion en Photoshop, Illustrator, Premiere o After Effects.

## Instalacion limpia

Esta rama es una aplicacion local privada, no un paquete npm publico. Desde un clon del repositorio, conservar los dos lockfiles y ejecutar `npm ci` en `adobe/` y luego `npm ci` en `adobe/companion/`. El `npm pack --dry-run` se usa solo como auditoria del contenido distribuible: npm omite deliberadamente el `package-lock.json` de la raiz al crear un tarball.

La companion necesita Electron instalado localmente; no depende de una instalacion global. Los iconos de `ICONOS/CHEMSEX/` son contenido de preview y explican el tamano del paquete de auditoria. El `.npmignore` excluye caches, sesiones, logs, jobs y secretos; no excluye `generic-interface-layer/core/jobs/`, porque ese directorio contiene codigo runtime.
