# Generic Interface Layer

Capa local y agnóstica de host para convertir contexto incompleto en análisis, propuestas y acciones explícitas. El paquete no necesita Adobe, Blender, Electron, MobileCLIP ni una base de datos de assets para funcionar.

## Inicio rápido

Requiere Node.js 20 o superior.

```powershell
cd .\adobe\generic-interface-layer
npm test
npm run smoke
```

El smoke test trabaja sólo con fixtures locales. No abre Adobe, no graba pantalla, no ejecuta shell y no copia assets.

## Flujo

`contexto recibido → normalización → análisis → propuesta → autorización explícita → acción → resultado → auditoría`.

Los proveedores semánticos/visuales y los adaptadores de host son opcionales. Esta carpeta forma parte del paquete local de LUCIDA y puede separarse más adelante si se define un repositorio independiente.

Más detalle:

- [Matriz de extracción](docs/extraction-matrix.md)
- [Arquitectura](docs/architecture.md)
- [Seguridad y privacidad](docs/security-and-privacy.md)
- [Límites de fuentes](docs/source-boundaries.md)
- [Mapa histórico de LUCIDA](docs/legacy-lucida-map.md)
