# Seguridad y privacidad

## Principios

La capa asume que los archivos locales pueden contener trabajos privados y que un plugin puede entregar datos incompletos o malformados. El valor predeterminado es local, offline, mínimo y explícito.

## Fronteras de datos

- El núcleo procesa metadatos y contexto entregado por el usuario/host.
- No graba pantalla ni mantiene un capturador periódico.
- No copia assets, datasets, renders, modelos ni pesos.
- No solicita credenciales ni depende de un servicio remoto.
- Los providers pesados son opt-in y tienen que declarar su procedencia, versión y licencia.
- Los datos sensibles quedan fuera de fixtures, pruebas y contratos genéricos.

## Rutas y archivos

Las operaciones de catálogo y jobs deben recibir roots explícitos. La política rechaza rutas fuera de las raíces permitidas y segmentos sensibles por defecto, incluidos `.env`, credenciales, secretos, `private`, bases de datos concretas y nombres de proyectos sensibles. La capa nueva no hace descubrimiento indiscriminado de todo el disco.

Los jobs usan `input`, `work`, `output` y `events` separados. Cancelar cambia el estado y conserva la request para diagnóstico; no borra archivos automáticamente.

## Acciones

Una propuesta no es una acción. El ciclo es:

`proposed → authorized → running → completed/failed/cancelled/rolled-back`.

La autorización exige confirmación explícita, actor, permisos, origen, destino, riesgo y una clave de idempotencia. El núcleo no ejecuta el payload: el adaptador autorizado lo interpreta dentro de sus límites.

Las operaciones destructivas o irreversibles deben ser rechazadas o marcadas como no soportadas cuando el host no ofrece rollback. El usuario puede cancelar antes y, cuando exista soporte del host, durante la ejecución.

## Shell y procesos

No hay comandos, ejecutables, `argv`, PowerShell, `spawn`, `exec` ni procesos en los contratos o en el transporte genérico. Los payloads con claves de shell se rechazan. La ausencia de esta capacidad es deliberada: una integración concreta debe tener su propia revisión y permiso.

## Plugins y HTTP local

El bridge acepta sólo `context.update`, `action.result` y `health`. Los demás tipos se rechazan. El servidor HTTP expone health, contexto y acciones; no expone una ruta de ejecución arbitraria. En una integración real se debe mantener loopback, limitar tamaño de body, validar origen y añadir autenticación cuando el proceso no sea estrictamente local.

## Auditoría

Cada transición relevante puede registrarse como evento encadenado por hash. La verificación detecta alteraciones, eventos fuera de orden o una cadena rota. Los payloads de auditoría deben minimizar datos: IDs, estados, razones y hashes son preferibles a contenido privado.

## Pruebas de seguridad incluidas

- contexto incompleto sin excepción;
- hash e IDs deterministas;
- permiso denegado;
- path fuera de allowlist;
- payload con shell rechazado;
- acción cancelada y rollback no soportado;
- replay de sesión;
- provider pesado ausente sin romper el core;
- bridge con mensaje no permitido;
- fixture sin archivos sensibles ni binarios.

## Riesgos pendientes

Los adaptadores host-specific todavía necesitarán revisión de permisos, autenticación y manejo de errores. Un provider de embeddings requerirá evaluación de consumo de VRAM/RAM, modelo, licencia, procedencia y posible exposición de imágenes. La política no sustituye un modelo de amenazas del producto distribuido ni la revisión de cada plugin de Adobe.
