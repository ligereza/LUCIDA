# INSTAR: Advanced Output y autoasignación segura

INSTAR puede leer un preset XML exportado desde Resolume Advanced Output y
convertirlo en un modelo portable del venue. El flujo está diseñado para el
caso de llegar pocos minutos antes del show:

1. El operador entrega el preset de Advanced Output.
2. INSTAR lo lee sin abrir ni cambiar Resolume.
3. INSTAR conserva la composición, las pantallas, los dispositivos, las
   slices, sus InputRect, sus OutputRect y los warps.
4. El catálogo de visuales se cruza con el tamaño y la proporción del
   InputRect.
5. Se genera un plan revisable con asignaciones sugeridas, alternativas y
   motivos.
6. El VJ confirma las asignaciones antes de llevarlas a un showfile o a una
   sesión en vivo.

## Comando

Solo importar y validar el preset:

~~~powershell
python .\tools\resolume_adapter_cli.py instar-map "C:\Users\issvk\Documents\Resolume Arena\Presets\Advanced Output\VENUE.xml" --report "Z:\RESOLUME_ADAPTER\runs\venue-advanced-output-map.json"
~~~

Importar y cruzar con un informe o manifiesto de INSTAR:

~~~powershell
python .\tools\resolume_adapter_cli.py instar-map "C:\Users\issvk\Documents\Resolume Arena\Presets\Advanced Output\VENUE.xml" --catalog "Z:\RESOLUME_ADAPTER\runs\instar.json" --report "Z:\RESOLUME_ADAPTER\runs\venue-mapping-plan.json"
~~~

El alias resolume-output hace lo mismo. El catálogo puede ser el JSON
principal de instar o un AssetManifest generado por INSTAR.

## Tarjeta de prueba geométrica

Cuando el mapping parece correcto pero un círculo o un cuadrado llega ovalado,
la proporción del rectángulo no es suficiente. INSTAR compara el escalado
horizontal y vertical de InputRect y OutputRect y agrega en cada slice un
perfil `geometry` con la proporción esperada del círculo, el porcentaje de
deformación, el estado y la necesidad de una prueba física.

Para generar una tarjeta reproducible basada en el canvas de composición:

~~~powershell
python .\tools\resolume_adapter_cli.py instar-testcard "C:\Users\issvk\Documents\Resolume Arena\Presets\Advanced Output\VENUE.xml" `
  --output "Z:\RESOLUME_ADAPTER\runs\venue-geometry-testcard.mp4" `
  --duration 12 `
  --fps 30 `
  --report "Z:\RESOLUME_ADAPTER\runs\venue-geometry-testcard.json"
~~~

La tarjeta usa un color por `input_group`, etiqueta cada slice, dibuja
cuadrícula, bordes, círculo, cuadrado y una línea móvil. Los grupos que
comparten InputRect reciben la misma prueba de entrada, porque Resolume los
alimenta desde la misma región creativa. La tarjeta no modifica el XML ni el
showfile.

Un estado `PASS` solo significa que InputRect y OutputRect describen un
escalado uniforme bajo la suposición de píxeles cuadrados. Un `WARN`, `FAIL`
o `REVIEW` exige mirar la tarjeta en la salida real: un procesador LED, una
configuración de NVIDIA, el HDMI o una pantalla pueden volver a escalar la
señal después de Resolume.

## Input y Output no son lo mismo

Resolume documenta Input Selection como la selección y organización de la
región de la composición que alimenta una pantalla o slice. En el XML esto
aparece como InputRect. Es el espacio correcto para comparar la proporción de
una visual con la región creativa.

Output Transformation mueve, escala, voltea, enmascara o warpea los píxeles
que finalmente salen hacia la pantalla, tarjeta o procesador. En el XML esto
aparece como OutputRect y la información de Warper. Es el espacio correcto
para estudiar la entrega física, pero no para decidir por sí solo qué video es
artísticamente adecuado.

Por eso el plan usa InputRect como criterio principal y conserva OutputRect
como contexto de salida. Una slice puede tener un InputRect compartido por
varias salidas: INSTAR lo agrupa como input_group_id y lo interpreta como
posible fan-out, no como tres destinos creativos independientes.

## Cómo se recomienda el encuadre

Para cada asignación, INSTAR compara el aspect ratio de la visual con el de la
región de entrada y calcula dos escenarios:

- Fill: cubre toda la slice, conserva la proporción y cuantifica qué fracción
  del cuadro se recortaría.
- Fit: conserva todo el cuadro, mantiene la proporción y cuantifica qué
  fracción quedaría vacía.

La política actual elige Fill cuando el recorte es pequeño o moderado. Elige
Fit cuando Fill eliminaría demasiado contenido o cuando el nombre sugiere
texto, letras, logo, marca o nombre; también protege visuales con alpha. En
casos extremos conserva la recomendación, pero exige revisión. Stretch nunca
se propone automáticamente porque sí deforma la imagen.

La recomendación queda en cada assignment como scaling, con el modo de
Resolume, los porcentajes de crop y de espacio vacío, los ejes afectados y la
razón. También compara la proporción del InputRect con la del OutputRect. Si el
mapping introduce una diferencia relevante, scaling marca
mapping_distortion_risk y exige revisión aunque Fill o Fit estén bien elegidos.
Así la futura capa de aplicación no tiene que volver a interpretar el video:
solo valida el plan, revisa el riesgo geométrico y traduce scaling a Slice
Transform.

Cada visual recibe además match_quality: GOOD para una coincidencia
suficientemente sólida, POSSIBLE para una coincidencia que debe verificarse y
NO_GOOD_MATCH cuando la mejor opción sigue siendo demasiado lejana. En el
último caso INSTAR conserva el candidato más cercano como referencia, pero
eligible_for_auto_apply queda en false.

## Qué puede y qué no puede inferir

El plan sí puede:

- detectar canvas de composición, pantallas físicas o virtuales y dispositivos
  declarados;
- calcular ancho, alto, proporción y orientación aproximada de cada región;
- detectar slices repetidas, InputRect fuera del canvas y warps activos;
- ordenar visuales por proporción, cobertura de resolución, nombres y alpha;
- distinguir candidato fuerte, candidato posible y ausencia de material
  adecuado para una proporción extrema;
- indicar cuándo una sugerencia es ambigua o requiere revisión.

El plan no puede saber solamente desde este XML:

- el modelo, pixel pitch, puertos, firmware o layout interno del procesador
  LED;
- si el operador conectó todas las pantallas o solo una parte;
- la intención del VJ para dos superficies con la misma proporción;
- si una visual funciona estéticamente en una superficie concreta.

El resultado inicial es deliberadamente suggest_assignment_to_input_group:
no escribe showfiles, no mueve archivos y no transmite comandos al procesador.
Una futura etapa podrá aplicar un plan sobre una copia explícita del showfile,
pero debe conservar esta revisión como barrera de seguridad.

Cuando una superficie no tiene un candidato fuerte por proporción, el plan
incluye `fallback_strategies`. Es el handoff hacia NAYADE: propone `pattern` o
`marquee` sobre el `input_group_id` correcto, con eje, candidatos y obligación
de preview. Así una visual 16:9 puede probarse en un banner sin estirarla ni
tratar la sugerencia como una asignación automática.

## Evidencia del preset

El importador conserva la ruta de origen, el nombre del preset, la versión de
Resolume, los identificadores de pantalla y slice, los puntos geométricos y
los dispositivos declarados. No copia el XML al repositorio ni incorpora
medios pesados.
