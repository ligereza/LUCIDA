# Arquitectura RESOLUME_ADAPTER por etapas y componentes

Estado: actualizado para la implementación INSTAR FFGL
Fecha: 2026-09-16

> Corrección de arquitectura: la versión anterior de este documento describía
> INSTAR como herramienta externa y reservaba el plugin FFGL para IMAGO. Esa
> definición queda supersedida en la rama actual: `INSTAR` es el plugin nativo
> de Resolume para el VJ y genera `AdvancedOutput.xml`; el parser Python de
> INSTAR es su acompañante offline para preparar perfiles, no un requisito de
> XML externo.

## Decisión principal

RESOLUME_ADAPTER no debe convertirse en tres versiones del mismo plugin. Las palabras
biológicas describen **cuándo** se usa una herramienta; los tipos de componente
describen **qué** hace. El código y los perfiles se comparten.

```text
                 RESOLUME_ADAPTER
                   │
     ┌─────────────┼─────────────┐
     │             │             │
   Probe         Guard         Bridge
  medir        corregir      conectar
     │             │             │
     └─────────────┼─────────────┘
                   │
          Signal Profile + Rules
                   │
       ┌───────────┼───────────┐
       │           │           │
    Python       FFGL        XIO
   offline       live      monitoring
```

Las etapas de uso quedan como una taxonomía independiente:

| Etapa | Uso principal |
|---|---|
| `INSTAR` | PRE SHOW y guía VJ: perfil de superficies, mapping y XML |
| `NAYADE` | SOUNDCHEK: prueba estable, handoff y routing con el house |
| `IMAGO` | SHOW: operación real en vivo dentro de Resolume |

INSTAR tiene dos superficies coordinadas: el plugin FFGL Capture de venues y el
parser offline que prepara entradas PDF/PNG/SVG. En el plugin, `XML_PLANES`
lee los `InputRect` del Advanced Output como la composición frontal y crea
exactamente un plano por `Slice`. No deduce una pantalla principal, banners,
tótems o tarima desde el XML. `Depth` es un valor global y `SliceDepths` es
una lista opcional alineada con el orden real de los slices. `VENUE_3D`
conserva el recorrido JSON de FLUJO y `RASTER_PIXEL_MAP` conserva la
inspección plana. `MapFile` puede texturizar los planos XML si corresponde a
la misma composición y `TemplateXML` continúa siendo la autoridad de routing
para la exportación explícita. Tras una exportación correcta, `OutputXML` se
recarga automáticamente como fuente del preview sin sobrescribir el template.
`INSTAR_3D.dll` recibe
OBJ/MTL para visualización de modelos y no genera XML. La exportación raster de
INSTAR es independiente del visualizador 3D; ambos comparten escena/render/cámara
donde corresponde.
Los
reportes y estadísticas son evidencia transversal, no una cuarta etapa.

## Tipos de componente

### Probe

Mide y explica. No altera el sistema.

Ejemplos:

- `Media Probe`: codec, resolución, FPS, alpha, VFR, luminancia y riesgos.
- `Output Probe`: GPU, monitor, EDID, resolución, Hz, color space y rango.
- `House Probe`: captura, input lock, formato, bus, destino y grupo de salidas.
- `Pattern Probe`: PLUGE, rampa, barras, checkerboard y pruebas de movimiento.

Los probes pueden ser Python, PowerShell o una herramienta portable. No deben
ser FFGL si necesitan inspeccionar todo el archivo, consultar USB o leer una
consola de video.

### Guard

Corrige o contiene una señal en tiempo real. Aquí vive el plugin FFGL.

Primera familia prevista:

- `Signal Guard`: rango, niveles, black level y gamma.
- `Banding Guard`: debanding y dithering controlado.
- `Temporal Guard`: estabilización de luminancia y deflicker.
- `Output Safe`: limitación o protección de flashes y valores extremos cuando
  sea técnicamente viable.

El primer FFGL pertenecerá a `IMAGO`. Tendrá identidad por defecto
y bypass inmediato. Las correcciones se limitarán a un perfil conocido o a
parámetros manuales explícitos.

### Bridge

Conecta RESOLUME_ADAPTER con otros sistemas sin procesar la imagen en el hilo de render.

Ejemplos:

- `XIO Bridge`: recibe monitoreo pasivo, OSC, Art-Net, sACN, timecode y eventos.
- `House Adapter`: normaliza información de un procesador o switcher.
- `Spout Bridge`: comparte frames en Windows cuando el flujo lo necesita.
- `OSC Bridge`: entrega estado a Resolume u otras herramientas.

El Bridge corre como proceso externo o en un hilo controlado fuera del render.
El FFGL carga un snapshot del perfil y no abre USB, red ni subprocesses durante
la llamada de dibujo.

### Record

Guarda evidencia y estadísticas. No tiene que ser un plugin de Resolume.

Incluye:

- perfil usado;
- configuración observada;
- frame time, FPS efectivo y eventos de lock;
- cambios de ruta o handoff;
- clips y hashes involucrados;
- advertencias y acciones tomadas;
- comparación entre soundcheck y show.

## Flujo de un show

```text
INSTAR
  media + sistema + composición
        ↓
NAYADE
  SOUNDCHEK + FIJO ↔ VJ ↔ CONSOLA ↔ destinos
        ↓
IMAGO
  Resolume + FFGL + perfil congelado
```

Las estadísticas, logs y perfiles finales se guardan como salida de cada
etapa. No habrá un plugin post-show separado en la primera arquitectura.

## Contratos compartidos

### Signal Profile

Un único esquema describe la señal, independientemente del fabricante:

```json
{
  "schema_version": "1.0",
  "source": {
    "resolution": "1920x1080",
    "fps": 60,
    "color_model": "RGB",
    "range": "full",
    "transfer": "sRGB",
    "primaries": "BT.709",
    "bit_depth": 8
  },
  "capture": {
    "resolution": null,
    "refresh_hz": null,
    "format": null,
    "lock": null
  },
  "house": {
    "input": null,
    "bus": null,
    "destinations": [],
    "outputs": []
  },
  "processor": {
    "vendor": "unknown",
    "model": "unknown",
    "read_only": true,
    "confidence": 0.0
  },
  "recommendation": {
    "range_transform": "identity",
    "gamma_transform": "identity",
    "deband": false,
    "deflicker": false
  }
}
```

El perfil debe distinguir siempre:

- **declared**: lo que dice el hardware;
- **observed**: lo que ve Windows, la GPU o una capturadora;
- **inferred**: hipótesis calculada por RESOLUME_ADAPTER;
- **confidence**: confianza de cada dato.

### Capability profile

Los adaptadores de NovaStar, Colorlight, Barco, Analog Way u otros no deben
crear algoritmos nuevos. Sólo traducen su información al `Signal Profile` y
declaran sus capacidades:

```text
supports_read_only_query
supports_input_format
supports_output_routing
supports_gamma_read
supports_black_level_read
supports_telemetry
```

Si una capacidad no existe o no está verificada, se marca como `unknown` y se
mantiene el modo seguro.

## Cómo evitar duplicación y versiones incompatibles

1. **Un solo esquema de perfil** para Python, FFGL y XIO.
2. **Un solo conjunto de casos de prueba** con clips, rampas, flashes,
   degradados y cambios de escena.
3. **Un solo catálogo de transformaciones**: rango, gamma, LUT, deband y
   temporalidad; no una implementación diferente por fabricante.
4. **Adaptadores delgados**: el hardware sólo aporta datos normalizados.
5. **Una DLL FFGL con varias entradas**, si resulta compatible con el SDK, para
   compartir el núcleo sin duplicar binarios innecesariamente.
6. **Versionado por contrato**, no por copia: un plugin declara qué versión de
   `schema_version` y qué capacidades necesita.
7. **Fixtures sintéticos** para probar los algoritmos sin depender de un
   procesador real.
8. **Perfil congelado durante el show**: los cambios externos requieren una
   recarga explícita y nunca deben aparecer a mitad de un frame.

## Cómo se presentan a los colegas

La marca visible debe ser humana y técnica al mismo tiempo:

```text
IMAGO
Corrige niveles, negros y gamma durante el show.
Host: Resolume / FFGL
Modo: seguro, reversible, sin conexión al procesador

NAYADE
Verifica captura, routing, escala y destinos antes de salir.
Host: Windows / XIO / house video
Modo: sólo lectura
```

La web puede ordenar por etapa, pero cada ficha debe mostrar también:

- problema que resuelve;
- momento recomendado;
- entrada y salida;
- host requerido;
- hardware compatible;
- cambios que realiza;
- límites conocidos;
- evidencia de pruebas;
- versión de contrato;
- licencia.

Así una persona no necesita entender `IMAGO` para encontrar “corregir negros
lavados durante el show”.

## Primera implementación

### Paso 1: `INSTAR`

Plugin FFGL de Resolume para el VJ, acompañado por un parser offline:

- diagnostica media, codecs, resolución, FPS y alpha;
- prepara o valida DXV;
- registra estado de GPU, disco, memoria y temperatura;
- genera el perfil inicial de señal;
- genera un `AdvancedOutput.xml` válido desde el canvas y el pixel-map raster u
  OBJ;
- muestra una guía visual de bajo consumo durante la preparación y el show;
- el parser offline rasteriza PDF y prepara entradas cuando la fuente no es raster.

Funciones nuevas de conocimiento y preparación:

- **VENUE**: identifica la sede física, separándola de la marca o cadena;
  consulta montajes anteriores y muestra sus niveles de confianza;
- **BASE DE DATOS PUBLICA**: incorpora reportes colaborativos de VJ,
  iluminación y sonido, conservando evidencia, fechas, autores, conflictos y
  versiones históricas;
- ingiere paquetes con Advanced Output XML, composiciones `.avc`, showfiles,
  exports de patch, capturas, fotos y configuraciones técnicas autorizadas;
- extrae un perfil sanitizado con canvas, slices, coordenadas, warping,
  resoluciones, versiones y dispositivos, sin publicar automáticamente rutas
  privadas ni archivos originales;
- compara la huella técnica y visual de un aporte con venues y montajes
  existentes, generando candidatos en vez de fusionar datos sin revisión;
- entrega a `NAYADE` una hipótesis de montaje para que el equipo la confirme
  durante el SOUNDCHEK.

La base no debe modelar sólo “qué tiene un venue”. Debe relacionar:

```text
marca → sede física → evento → montaje observado → evidencias → artefactos
```

La fecha del evento, la fecha de observación y la fecha del archivo se guardan
por separado. Los nombres de archivos y los identificadores internos de
Resolume son pistas de asociación, no pruebas suficientes de ubicación.

#### Primera función técnica a atacar

El acompañante offline de `INSTAR` es un **Venue Profile Importer** local. Recibirá
una carpeta o un ZIP de trabajo y producirá un perfil técnico reutilizable:

```text
aporte.zip
      ↓
lectura de XML / AVC / evidencias
      ↓
sanitización de rutas e identificadores privados
      ↓
venue-profile.json
      ↓
revisión y asociación con la base pública
```

El MVP debe leer primero los Advanced Output XML porque ya contienen la
información más accionable para VJ: resolución de composición, pantallas,
slices, rectángulos de entrada y salida, warping, gamma y dispositivo de
salida. La lectura de `.avc`, showfiles de luces y archivos de sonido se
incorporará como extractores adicionales sobre el mismo contrato de artefactos.

### Paso 2: `NAYADE`

Herramienta externa de soundcheck, sólo lectura:

- captura la salida local de Windows/GPU;
- registra EDID, resolución, Hz y color space cuando estén disponibles;
- incorpora datos de XIO si hay telemetría;
- permite declarar input, bus y destinos cuando la consola no tiene API;
- genera `Signal Profile` y reporte;
- verifica si el problema es routing, canvas, escala, formato o color.

### Paso 3: `IMAGO`

Capa posterior de observación/propuestas; no es el plugin FFGL nativo actual:

- carga el perfil al iniciar;
- aplica sólo la transformación recomendada;
- ofrece bypass y control manual estándar del host;
- no escribe en la consola ni en el procesador;
- no depende de Python durante el render;
- comienza con rango/negros/gamma, dejando debanding y deflicker para módulos
  posteriores del mismo núcleo.

Los resultados estadísticos quedan como salida de `INSTAR`, `NAYADE` e `IMAGO`:

- comparan soundcheck y show;
- encuentran cambios de FPS, lock, rutas y frame time;
- miden si una corrección redujo el síntoma o sólo lo ocultó;
- proponen una nueva versión del perfil sin aplicarla automáticamente.

## Decisiones de seguridad

- El comportamiento por defecto es passthrough.
- No se cambia hardware de forma automática.
- No se escribe en USB, red, firmware, receiving cards ni mapping en el MVP.
- Los adaptadores desconocidos funcionan en modo manual y baja confianza.
- Un fallo de RESOLUME_ADAPTER no debe impedir que Resolume emita la señal original.
- No se ejecutan procesos persistentes desde el plugin de render.
- Los perfiles y reportes registran fecha, versión, equipo y nivel de confianza.

## Resultado

La unidad de reutilización no será el plugin completo, sino:

```text
algoritmo + perfil + fixtures + reglas + adaptadores de host
```

El mismo conocimiento puede aparecer como CLI, herramienta de soundcheck,
plugin FFGL o puente XIO sin volver a programar la solución desde cero.
