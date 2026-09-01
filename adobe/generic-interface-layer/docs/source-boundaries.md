# Límites de fuentes

## Regla de conservación

El árbol original se conserva. Esta extracción sólo agrega `generic-interface-layer/` dentro del paquete LUCIDA en una rama aislada. No se borra, mueve ni reescribe contenido original como parte de esta etapa.

## Incluido

Se incluyeron implementaciones nuevas y pequeñas, escritas contra contratos genéricos:

- contratos de contexto, acción y evento;
- normalización y análisis determinista;
- ranking de propuestas;
- lifecycle de acciones;
- auditoría y replay;
- seguridad y jobs locales;
- catálogo de metadatos y búsqueda textual;
- interfaces opcionales visual/semántica;
- descriptors de adaptadores;
- transportes HTTP local, cola de archivos y plugin bridge;
- fixtures JSON, tests y documentación.

## Excluido explícitamente

No se copiaron al paquete nuevo:

- imágenes, SVG, PNG, JPG, renders, PSD, AI, BLEND, videos o audio;
- trabajos Chemsex, health/harm-reduction, láminas, iconos o assets personales;
- `rd_database_complete` y cualquier base de recursos concreta;
- bases GDKB, exports o corpus de terceros;
- `remote_imports`, clones y descargas cuya licencia/procedencia no esté confirmada;
- MobileCLIP, pesos, checkpoints, caches, CUDA o entornos virtuales;
- `.env`, tokens, credenciales, secretos y configuraciones locales;
- `forma_viva_mvp` y otros proyectos específicos;
- `umbrella`, `d3`, `three.js`, `effect`, `rxjs`, `stdlib` y librerías grandes del árbol;
- UI Electron, UXP, JSX, scripts de producción y escenas Blender completas.

Los nombres de algunas fuentes aparecen en esta documentación sólo para dejar trazabilidad de la exclusión; no representan datos copiados ni dependencias runtime.

## Clasificación operativa

| Clase | Tratamiento |
|---|---|
| A núcleo | Puede entrar si no depende de un host ni de datos concretos |
| B provider | Entra detrás de interface; sus modelos/datasets permanecen opcionales |
| C presentación | Se mantiene fuera del núcleo; puede consumir view-model |
| D adaptador | Entra como traducción periférica, nunca como requisito central |
| E transporte | Sólo protocolos allowlisted y auditables |
| F proyecto/datos | No se copia |
| G experimental | No se copia hasta tener pruebas, licencia y propósito |

## Licencias y procedencia

Un provider futuro debe registrar fuente, versión, licencia, hash del artefacto y restricciones de uso. No se agrega una dependencia sólo porque exista en el árbol local. Las referencias a documentación o ejemplos oficiales pueden guiar un adaptador, pero no se convierten automáticamente en código runtime.

## Qué falta para separar a un repo

El paquete usa `generic-interface-layer` como núcleo técnico de LUCIDA; su repositorio público y remoto se pueden separar posteriormente sin mezclar datos de proyectos.
