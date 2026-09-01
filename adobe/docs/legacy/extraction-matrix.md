# Matriz de extracción

## Criterio

La extracción conserva capacidades genéricas, contratos y decisiones comprobables. No copia la aplicación SVG, assets, renders, datasets, credenciales, corpus de licencia dudosa ni experimentos no verificados. La categoría indica el tratamiento:

- **A — núcleo genérico:** se puede reutilizar sin conocer un host concreto.
- **B — conocimiento/proveedor:** búsqueda, catálogo o modelo opcional; no bloquea el núcleo.
- **C — presentación:** interfaz visual, Electron o componentes de interacción.
- **D — adaptador:** traducción a un host externo, con contrato periférico.
- **E — transporte:** comunicación local, cola o puente.
- **F — datos/proyecto específico:** queda fuera de la extracción.
- **G — experimental/no verificado:** queda fuera hasta tener pruebas, licencia y frontera clara.

## Mapa de origen y destino

| Origen | Capacidad observada | Categoría | Destino | Dependencia | Estado | Verificación | Decisión |
|---|---|---:|---|---|---|---|---|
| `agent-toolkit/contracts/context-schema.json` | Contrato de contexto | A | `core/contracts/context.schema.json` | Ninguna | Extraído y generalizado | Contexto incompleto | Se eliminan requisitos exclusivos de Adobe |
| `agent-toolkit/contracts/message-schema.json` | Envelopes de mensajes | A/E | contratos y transportes | Ninguna | Extraído conceptualmente | Bridge allowlist | Sólo mensajes de contexto, acción y resultado |
| `agent-toolkit/companion/selection.schema.json` | Selección persistible | A | contrato de contexto/fixtures | Ninguna | Generalizado | Fixture replay | Se conserva la forma, no la UI |
| `agent-toolkit/src/tools/context.mjs` | Normalización, estado, recomendaciones e inserción | A/B/D/E mezcladas | `core/context`, `core/analysis`, `core/proposals`, `core/actions`, `transports` | Estado y rutas del toolkit actual | Separado | Tests de flujo | Sólo se extraen responsabilidades; no se copia el módulo |
| `agent-toolkit/src/tools/context-analysis.mjs` | Tópicos, capas, paleta y áreas libres | A/B | `core/analysis` | Ninguna | Extraído de forma determinista | Incomplete-context test | Se excluyen vocabularios específicos del proyecto |
| `agent-toolkit/src/jobs.mjs` | Directorios, estados y cancelación de jobs | A | `core/jobs` | Sistema de archivos local | Extraído | Job cancellation test | Sin ejecución de comandos ni borrado |
| `agent-toolkit/src/audit.mjs` | Registro NDJSON | A | `core/audit` | Ninguna | Replanteado con cadena hash | Audit verification test | El núcleo usa eventos puros; el almacenamiento queda periférico |
| `agent-toolkit/src/utils.mjs` | Allowlist de rutas y salida segura | A/E | `core/security` | Sistema de archivos | Extraído | Path/privacy test | Se endurecen segmentos denegados y payloads de shell |
| `agent-toolkit/src/tools/local-catalog.mjs` | Inventario local y búsqueda | B | `providers/local-catalog`, `providers/text-search` | FS local | Contrato extraído | Metadata fixture | No copia ni indexa corpus sensible por defecto |
| `agent-toolkit/src/tools/asset-search.mjs` | Ranking por texto/semántica | B | `providers/text-search`, `providers/semantic-search` | Modelos opcionales | Interface extraída | Optional provider test | El modelo no es requisito de instalación |
| `agent-toolkit/src/tools/mobileclip.mjs` | Embeddings visuales | B/G | `providers/visual-search`, `providers/semantic-search` | Runtime/modelo externo | Sólo interface | Provider unavailable test | No se copia MobileCLIP, pesos ni cache |
| `agent-toolkit/src/tools/project-inventory.mjs` | Lectura de proyectos locales | B/D | proveedor de catálogo/adaptadores | Rutas del usuario | Fuera del core | Boundary review | Debe recibir roots explícitos |
| `agent-toolkit/src/tools/catalog-groups.mjs` | Agrupación de assets | B | proveedor local | Metadata | Fuera del core mínimo | Pendiente de integración | Se puede conectar como provider |
| `agent-toolkit/companion/*` | Ventana flotante, drag y preview | C | `clients/companion/view-model.mjs` | Electron | Contrato aislado | Reducer test | La UI actual no entra al núcleo |
| `agent-toolkit/adobe/*` y UXP/JSX | Contexto/importación en Adobe | D | `adapters/adobe` y `transports/plugin-bridge` | Photoshop/Illustrator/etc. | Descriptor periférico | Hostless core test | El núcleo corre sin Adobe |
| `agent-toolkit/adapters/blender/*` | Contexto y operaciones Blender | D | `adapters/blender` | Blender | Descriptor periférico | Hostless core test | No se copian escenas ni Geometry Nodes |
| `agent-toolkit/adapters/gdkb/*` | Integración con GDKB | D | `adapters/gdkb` | Servicio/base externa | Descriptor periférico | Contract review | No se copian bases ni fixtures |
| `agent-toolkit/adapters/image/*` | Procesamiento/preview de imágenes | B/D | providers o `adapters/svg` | Librerías de imagen | No requerido | Optional provider test | Se deja como integración futura |
| `agent-toolkit/src/server.mjs` | HTTP local, rutas, límites y auth | E | `transports/local-http` | Node HTTP | Reimplementado mínimo | Offline smoke | No se heredan rutas de ejecución |
| `agent-toolkit/integrations/*` | Fuentes, mapas y referencias | D/G | `docs` / adaptadores | Servicios externos | Sólo auditado | Boundary review | No son dependencias runtime |
| `agent-toolkit/scripts/*mobileclip*` | Descarga/indexación de embeddings | B/G | provider opcional | Red, CUDA/modelo | Excluido | No-sensitive-copy check | Requiere decisión explícita de modelo y fuente |
| `remote_imports/*` | Importaciones o clones de terceros | D/G | Ninguno por ahora | Red/repos externos | Excluido | Source boundary review | No se copia sin licencia y propósito |
| `rd_database_complete/*` | Base/recursos específicos | F | Ninguno | Datos de proyecto | Excluido | No-sensitive-copy check | No entra al paquete |
| raíces y proyectos `Chemsex*` | Trabajo editorial y assets sensibles | F | Ninguno | Datos personales/proyecto | Excluido | No-sensitive-copy check | No entra al paquete |
| `forma_viva_mvp/*` | Experimento/proyecto concreto | F/G | Ninguno | Proyecto externo | Excluido | Boundary review | No entra al paquete |
| `umbrella`, `d3`, `three.js`, `effect`, `rxjs`, `stdlib` | Librerías amplias del árbol | G/B | Ninguno por ahora | Dependencias no minimizadas | Excluido | Dependency review | Se agregan sólo si un provider lo necesita |

## Estado de la extracción

La carpeta nueva contiene únicamente código, contratos, fixtures JSON, pruebas y documentación. No contiene `.png`, `.jpg`, `.svg`, `.psd`, `.blend`, modelos, pesos, caches ni bases de datos. Los adaptadores son descriptores para impedir que el núcleo importe implementaciones host-específicas accidentalmente.

## Siguiente frontera

Antes de mover esta carpeta a un repositorio separado faltan el path destino, el remoto y la decisión de nombre público. Hasta entonces el paquete permanece como staging en la rama aislada y el árbol original queda intacto.
