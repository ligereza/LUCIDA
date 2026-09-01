# Context Shelf — Photoshop UXP bridge

Primer vertical slice del sistema: publica el documento y la capa activa en el
bridge local, y consume órdenes de inserción generadas por la app flotante.

## Carga local

1. Iniciar `npm run companion:start` desde `C:\IA\LUCIDA\adobe`; la app flotante inicia el bridge automáticamente. Si se prueba el panel sin la app, iniciar `npm run server` manualmente.
2. Abrir UXP Developer Tool.
3. Agregar este `manifest.json` y cargarlo en Photoshop.
4. Dejar el panel abierto mientras se prueba la app flotante.

El panel no es la interfaz final; funciona como puente de contexto y consumidor
de órdenes. La interfaz principal será `companion/`.
