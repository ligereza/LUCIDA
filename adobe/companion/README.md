# Context Shelf companion

Ventana flotante local del primer vertical slice. Lee el último snapshot del
host Adobe desde el bridge y encola inserciones para la sesión activa.

## Ejecutar

La app inicia automáticamente el bridge local si todavía no está corriendo.
Sólo necesitas una terminal:

```powershell
cd .\adobe
npm run companion:start
```

También puedes iniciarla directamente desde `companion`:

```powershell
cd .\adobe\companion
npm start
```

Si el bridge ya estaba iniciado, la app lo reutiliza y no crea otro proceso.

Después carga `../adobe-context-shelf/photoshop-uxp/manifest.json` en UXP
Developer Tool y abre el panel Context Shelf dentro de Photoshop.

Antes de la primera prueba, la biblioteca local se puede cargar o actualizar
con:

```powershell
cd .\adobe
npm run tool -- asset index-local --max-files 30000
npm run tool -- asset catalog-stats
```

El índice incluye solo los SVG/PNG generados o creados dentro del proyecto y
sus variantes por lámina. Las colecciones descargadas de Bioicons y
Healthicons se mantienen fuera de Context Shelf. El bridge lo reutiliza en cada
recomendación y sólo se vuelve a indexar cuando se solicita una actualización.

El análisis que acompaña cada snapshot detecta el tema de la capa, términos
visuales, paleta enviada por el host, capas que ocupan espacio y rectángulos
libres reales. El popup prioriza los recursos locales insertables; las fuentes
remotas se usan como respaldo.

La pestaña `Explorar` navega el índice por tema, color dominante, tamaño de
archivo, dimensiones, proporción, formato, tipo y variante. Cada grupo se
puede abrir y recorrer por páginas; los recursos conservan su ruta directa y
su miniatura.

La pestaña `Proyecto` muestra el inventario completo de un proyecto por
lámina. Cada lámina se divide en grupos semánticos y cada grupo expone sus
capas editables y todas las variaciones encontradas. Para Chemsex conecta los
recursos del proyecto, las variaciones históricas de `rd_database_complete` y
los manifiestos de capas de los pilotos regenerados. `Todo` permite revisar
el proyecto completo; al elegir una lámina se habilita el check de selección,
que queda guardado por proyecto y lámina. El botón `↻` vuelve a indexar para
incorporar archivos nuevos.

Cada tarjeta local se puede arrastrar directamente desde el popup hacia el
canvas de Photoshop o Illustrator. Es un arrastre nativo de archivo y no
depende del bridge; la aplicación de Adobe debe estar abierta y el documento
visible como destino. El botón `+` conserva la inserción contextual mediante
el bridge/plug-in.

La ventana usa una API IPC allowlisted y sólo habla con
`http://127.0.0.1:47921`. No ejecuta comandos JavaScript recibidos desde la
red.
