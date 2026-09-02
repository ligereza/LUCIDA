# Context Shelf — Photoshop UXP bridge

Primer vertical slice del sistema: publica el documento y la capa activa en el
bridge local, y consume órdenes de inserción generadas por la app flotante.

## Carga local

1. Desde la raiz del repositorio, entrar en `adobe` y ejecutar `npm run companion:start`; la app flotante inicia el bridge automaticamente. Si se prueba el panel sin la app, iniciar `npm run server` manualmente.
2. Abrir UXP Developer Tool.
3. Agregar este `manifest.json` y cargarlo en Photoshop.
4. Dejar el panel abierto mientras se prueba la app flotante.

El manifiesto usa la version 5 de UXP y requiere Photoshop 23.3.0 o
posterior para disponer del ciclo `show`/`hide`/`destroy` que detiene el
polling cuando el panel deja de estar activo.

El panel no es la interfaz final; funciona como puente de contexto y consumidor
de ordenes. La interfaz principal sera `companion/`. La raiz del paquete se
resuelve desde la carpeta del plugin para que el checkout pueda moverse sin
editar una ruta fija.
