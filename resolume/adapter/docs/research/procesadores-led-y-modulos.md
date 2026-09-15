# Procesadores LED, módulos y NAYADE

## Decisión de arquitectura

NAYADE separa tres capas que en un soundcheck suelen confundirse:

1. **Señal**: NVIDIA/Resolume, resolución, FPS, RGB Full/Limited y formato de salida.
2. **Procesador**: equipo que recibe HDMI/DP/SDI, escala o enruta, aplica color y envía datos a las tarjetas receptoras.
3. **Superficie**: módulos o gabinetes LED, pixel pitch, resolución física, indoor/outdoor, brillo, frecuencia de refresco, calibración y topología.

El HDMI puede entregar resolución, frecuencia y formato de color, pero normalmente no entrega de forma confiable el pixel pitch, el modelo del módulo, si el panel es indoor/outdoor ni la topología de receiving cards. Esos datos deben venir del procesador/software del fabricante, de un fixture profile, de una etiqueta/foto o del técnico. Por eso el snapshot admite hechos con origen y confianza en vez de inventar datos.

## Familias que se encuentran con frecuencia

| Familia | Papel habitual | Transporte o software | Qué puede aportar a NAYADE |
| --- | --- | --- | --- |
| NovaStar VX/MCTRL/VX Pro | Controlador LED común en producciones pequeñas y medianas | USB de control, Ethernet y software del fabricante según modelo | Identidad, señal de entrada, rango/color, parámetros de imagen, configuración de pantalla y patrones en modelos compatibles |
| Colorlight X y familias 5A | Controlador LED y ecosistema de receiving cards | Ethernet/USB/software según modelo y firmware | Identidad y capacidad; los campos exactos deben confirmarse por modelo |
| Brompton Tessera | Procesamiento LED de alta exigencia | Management Ethernet, Tessera Remote, HTTP/Telnet y software propio | Procesador, fixtures, pitch declarado por fixture, mapping, scaling/cropping, estado y patrones |
| Megapixel HELIOS | Procesamiento LED para sistemas y tiles compatibles | Ethernet y software propietario | Compatibilidad de tile, capacidad, salud, fallas de pixel y configuración del proyecto |
| Barco/Analog Way y similares | Scaler/switcher de la cadena, no necesariamente el controlador LED final | Ethernet/USB/software propietario | Resolución, entradas, salidas, escalado y ruteo; deben catalogarse como otro equipo de la cadena |
| Linsn/TS/clones y equipos sin identificación | Controlador o receiving system variable | Cable y protocolo dependen del equipo | Solo observación manual hasta identificar modelo; no se escribe nunca por defecto |

La primera implementación no afirma que todas las capacidades estén disponibles en todos los modelos. El catálogo registra la familia y el nivel de certeza; la capacidad real debe quedar ligada al modelo y firmware.

## Qué descargamos y por qué

- [Manual oficial NovaStar VX600](https://oss.novastar.tech/uploads/2023/06/VX600-All-in-One-Controller-User-Manual-V1.3.0.pdf): sirve como primer patrón de parámetros y de límites de seguridad.
- [Manual oficial NovaLCT V5.5.0](https://oss.novastar.tech/uploads/2024/02/NovaLCT-LED-Configuration-Tool-for-Synchronous-Control-System-User-Manual-V5.5.0.pdf): referencia para receiving cards y configuración del sistema LED.
- [Comparativa oficial NovaStar VX400/VX600/VX1000](https://www.novastar.tech/product/detail.html?catid=3&id=35): relaciona modelo con entradas, salidas y capacidad de carga.
- [Manual oficial Brompton Tessera](https://www.bromptontech.com/wp-content/uploads/2021/03/Tessera-User-Manual-V3.1-Rev-A.pdf): referencia para fixtures, pitch, mapping, test patterns y operación profesional.
- [Guía oficial Megapixel HELIOS](https://megapixelvr.com/wp-content/uploads/2023/09/megapixel-helios-processing-system-user-guide.pdf): referencia para tiles, capacidad y estado del sistema.
- [Índice oficial de descargas Colorlight](https://en.colorlightinside.com/service/download/index_2.html?cat=201): fuente para emparejar X6/X7/X20 y firmware antes de crear un adaptador.
- [Investigación abierta de NovaStar](https://github.com/sarakusha/novastar): referencia de transporte/protocolo; no se considera autorización para escribir en un equipo real.
- [Investigación abierta Colorlight 5A](https://github.com/haraldkubota/colorlight): referencia limitada a esa familia, no un protocolo universal.

Los manuales descargados quedan en `docs/references/processors`. El catálogo conserva el enlace oficial y la ruta local para que una futura revisión pueda detectar si un perfil quedó desactualizado.

## Cómo se relaciona con indoor/outdoor y pixel pitch

El perfil de módulo debe guardar, como mínimo:

- resolución física del fixture en píxeles;
- ancho y alto físicos;
- pixel pitch en milímetros;
- indoor/outdoor como dato declarado u observado;
- brillo nominal y frecuencia de refresco si se conocen;
- receiving card y modelo del módulo si están disponibles;
- fuente del dato: manual, etiqueta, foto, técnico, medición u observación.

El pitch permite validar si una resolución física y una dimensión declarada son coherentes: `ancho_mm ≈ píxeles_horizontal × pitch_mm`. No permite deducir por sí solo el estado del color, la calibración o la salud de los módulos. Un mismo procesador puede alimentar módulos distintos en cada salida.

## Regla de seguridad

El comando inicial de NAYADE solo enumera USB/COM y crea snapshots. No abre puertos, no envía bytes, no activa test patterns y no escribe. La detección por VID/PID o texto del descriptor es una pista, no una prueba. El siguiente adaptador debe exigir modelo confirmado, firmware, transporte y una captura/backup verificable antes de habilitar lecturas del protocolo; las escrituras quedan fuera de esta fase.

## Fuentes relacionadas con color

La documentación de [NVIDIA sobre RGB Dynamic Range](https://www.nvidia.com/content/Control-Panel-Help/vLatest/en-us/mergedProjects/Display/To_change_the_RGB_range.htm) confirma la diferencia entre Full 0–255 y Limited 16–235 y advierte que Full en una pantalla que no lo soporta puede producir colores incorrectos. El caso VC2 de RESOLUME_ADAPTER registra esa hipótesis, pero NAYADE no la da por confirmada sin registrar también el estado Limited→Full del procesador.
