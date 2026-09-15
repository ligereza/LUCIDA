# Integración RESOLUME_ADAPTER–Resolume MCP

Estado: diseño inicial  
Fecha: 2026-08-29

## Objetivo

Convertir a RESOLUME_ADAPTER en una capa de criterio técnico alrededor de Resolume:

- Resolume conserva la reproducción, composición y salida.
- El MCP de Resolume permite consultar y modificar lo que la API expone.
- RESOLUME_ADAPTER inspecciona media, sistema y señal; calcula riesgos; recomienda acciones
  y registra evidencia.
- Las acciones que cambian una composición requieren confirmación explícita.

RESOLUME_ADAPTER no debe intentar reemplazar Resolume ni convertirse en un asistente que
dispare acciones ambiguas durante un show.

## Qué aporta cada pieza

```text
Asistente compatible con MCP
          │
          ├── Resolume MCP ── Arena / Avenue / Wire
          │
          └── RESOLUME_ADAPTER ─────── media / sistema / señal / reglas / reportes
                                  │
                                  └── recomendación verificable
```

El MCP de Resolume permite construir y administrar composiciones, cargar
archivos, añadir o quitar efectos, capas, columnas y grupos. También permite
crear patches en Wire y escribir shaders ISF. Su uso está pensado principalmente
para construir y modificar, no para operar una presentación en vivo.

Referencia oficial: [Resolume MCP Servers](https://resolume.com/support/en/mcp-servers).

## Capacidades de RESOLUME_ADAPTER

### 1. Auditor de composición

Consulta la composición actualmente cargada y genera un informe humano y JSON:

- resolución de composición;
- FPS de composición;
- cantidad de decks, grupos, capas, columnas y clips;
- archivos utilizados y archivos ausentes;
- codec, resolución, FPS, alpha y VFR de cada medio;
- clips que no están en DXV cuando el host es Resolume;
- material sobredimensionado para la salida real;
- posibles puntos de presión de GPU, VRAM, CPU y disco;
- efectos o cadenas candidatas a pre-renderizar;
- nivel de confianza de cada conclusión.

Ejemplo de resultado:

```text
INSTAR / AUDITOR DE COMPOSICIÓN

WARN  14 clips no están en DXV.
WARN  6 clips son 3840×2160 para una composición 1920×1080.
WARN  3 clips tienen FPS variable.
INFO  La composición usa 8 capas activas y 2 efectos de composición.
PLAN  Convertir 14 clips a DXV Normal Quality.
PLAN  Crear versiones 1920×1080 de los 6 clips sobredimensionados.
PLAN  Pre-renderizar la cadena de efectos de 2 clips estables.
```

El auditor no modifica nada.

### 2. Planificador de optimización

RESOLUME_ADAPTER no debería aplicar automáticamente una receta genérica. Debe generar un
plan según:

- host: Resolume Arena o Avenue;
- resolución y FPS reales de salida;
- existencia de alpha;
- tipo de show: FLEX, SYNC o CRITICAL;
- potencia y memoria disponibles;
- prioridad visual del clip;
- posibilidad de repetir o reemplazar el archivo;
- margen de rendimiento deseado.

Cada acción se clasifica como:

- `SAFE`: sólo crea un reporte o una copia derivada;
- `REVIEW`: requiere aprobación del usuario;
- `BLOCKED`: no se ejecuta porque puede alterar routing, sincronía o salida.

### 3. Preparador de media

Usa el núcleo existente de RESOLUME_ADAPTER para:

- diagnosticar archivos;
- convertir a DXV cuando el destino sea Resolume;
- normalizar FPS a CFR;
- preparar versiones de resolución objetivo;
- conservar alpha sólo cuando exista realmente;
- generar hashes y manifiestos;
- validar el resultado después de convertir;
- conservar el original intacto.

El codec no es una decisión universal: DXV es una recomendación para Resolume,
no una regla para otros hosts.

### 4. Explicador de problemas

Ante una consulta como “¿por qué este show está pesado?”, RESOLUME_ADAPTER debe separar:

- problema de decodificación;
- problema de resolución o pixel rate;
- problema de efectos en tiempo real;
- problema de transferencia hacia VRAM;
- problema de memoria o disco;
- problema de salida, escalado o formato;
- problema externo de procesador LED, cableado, PWM o frecuencia.

La respuesta debe distinguir hechos medidos, inferencias y acciones sugeridas.

### 5. Generador de configuración repetitiva

Después de la revisión del usuario, el MCP de Resolume puede ayudar a ejecutar
tareas repetitivas como:

- crear capas o columnas;
- cargar clips preparados;
- añadir un efecto a un conjunto definido;
- organizar una composición;
- crear un patch inicial en Wire;
- generar variantes de textos o nombres.

RESOLUME_ADAPTER debe producir primero un resumen del cambio y guardar una copia del
estado anterior cuando sea posible. Las operaciones de mutación no pertenecen
al modo de emergencia ni al hilo crítico de render.

## Límites que debemos respetar

Según la documentación oficial, el MCP de Arena/Avenue actualmente no puede:

- crear o modificar screens y slices de Advanced Output;
- crear o modificar mappings de teclado, MIDI, DMX u OSC;
- crear, modificar o disparar cue points;
- aplicar o modificar presets;
- aplicar o modificar envelopes;
- leer o modificar dials del Dashboard;
- grabar la composición o renderizar clips.

Por tanto, RESOLUME_ADAPTER debe tratar Advanced Output, mappings, procesadores LED y
hardware como dominios separados, mediante sus propios probes y adaptadores.

## Flujo por etapas

### INSTAR

1. El usuario abre la composición.
2. RESOLUME_ADAPTER solicita una lectura del estado disponible.
3. RESOLUME_ADAPTER analiza los archivos localmente.
4. Genera un reporte de riesgos y un plan de optimización.
5. El usuario aprueba sólo las acciones deseadas.
6. Se preparan archivos derivados y un manifiesto del show.

### NAYADE

1. Se verifica la señal real de Windows/GPU/capturadora.
2. Se ejecutan patrones de prueba.
3. Se compara la composición declarada con la salida observada.
4. Se revisan escala, rango, gamma, FPS, lock y destinos.
5. Se congela un `Signal Profile` para el show.

El MCP de Resolume no reemplaza esta etapa porque no puede ver por sí solo todo
el camino entre Arena y la pantalla.

### IMAGO

Durante el show, RESOLUME_ADAPTER sólo debe observar y alertar:

- FPS efectivo;
- frame time;
- frames perdidos;
- consumo de GPU, CPU y VRAM;
- pérdida de lock o cambio de salida;
- eventos relevantes de Resolume;
- estado del perfil aprobado.

No se deben aplicar cambios automáticos de composición, mapping o procesador
durante la presentación.

## Contrato de una acción

Toda operación propuesta debe poder representarse así:

```json
{
  "action_id": "prepare-dxv-001",
  "stage": "INSTAR",
  "risk": "SAFE",
  "target": "media/loop-07.mp4",
  "reason": "Codec H.264; el host objetivo es Resolume.",
  "operation": "create_derived_media",
  "parameters": {
    "codec_profile": "resolume-dxv3-normal-no-alpha",
    "fps": 30,
    "resolution": "1920x1080"
  },
  "requires_confirmation": false,
  "reversible": true
}
```

Para una mutación de composición:

```json
{
  "action_id": "composition-add-effect-001",
  "stage": "INSTAR",
  "risk": "REVIEW",
  "target": "current-composition",
  "reason": "El usuario solicitó añadir el efecto a las capas seleccionadas.",
  "operation": "add_effect",
  "requires_confirmation": true,
  "reversible": true
}
```

## Primer entregable

El primer MVP de esta integración será un **auditor de composición Resolume**:

1. Recibe una exportación o snapshot de composición.
2. Extrae clips, rutas y parámetros disponibles.
3. Reutiliza `diagnose_file` para analizar cada medio.
4. Compara los medios con el perfil objetivo.
5. Devuelve un plan JSON con `SAFE`, `REVIEW` y `BLOCKED`.
6. No modifica Resolume todavía.

Después se añadirá la conexión MCP/REST para leer la composición directamente y,
en una etapa posterior, ejecutar acciones aprobadas.

La primera regla es que RESOLUME_ADAPTER pueda decir con evidencia **qué haría y por qué**
antes de tener permiso para hacerlo.
