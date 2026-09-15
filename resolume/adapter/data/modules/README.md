# Perfiles de módulos LED

Esta carpeta guarda perfiles físicos aportados por un venue, técnico o colega.
Cada perfil debe cumplir `schemas/module-profile.schema.json` y conservar la
fuente de cada dato. No se deben rellenar pitch, indoor/outdoor, brillo o
frecuencia “a ojo” si no existe una etiqueta, manual, ficha técnica,
medición o declaración explícita.

Datos mínimos recomendados por fixture:

- resolución física en píxeles;
- ancho y alto físicos;
- pixel pitch en milímetros;
- indoor/outdoor y nivel de confianza;
- modelo del módulo/gabinete y receiving card si se conocen;
- venue y procedencia del registro.

El `profile_id` se puede vincular desde un `NayadeProcessorSnapshot`. Si una
instalación combina módulos distintos, se registran como fixtures separados
dentro del mismo perfil de venue.
