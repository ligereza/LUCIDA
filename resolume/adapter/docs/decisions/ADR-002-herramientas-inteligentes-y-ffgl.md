# ADR-002: Separar herramientas inteligentes, integración y FFGL

**Estado:** Proposed
**Fecha:** 2026-08-28
**Decisores:** RESOLUME_ADAPTER

## Contexto

RESOLUME_ADAPTER debe entregar herramientas gratuitas y fáciles de usar para colegas VJ. Los casos de uso iniciales son el diagnóstico de medios, la detección de posibles causas de flicker y la preparación de conversiones a DXV.

FFGL se ejecuta dentro del pipeline de video de Resolume y es apropiado para procesamiento de frames en tiempo real. No es una interfaz general para inspeccionar archivos, convertir medios o diagnosticar toda la cadena de salida.

## Decisión

RESOLUME_ADAPTER tendrá tres capas separadas:

1. **Herramientas externas:** núcleo Python para analizar archivos, generar reportes, preparar trabajos y validar resultados.
2. **Integración con Resolume:** futuras herramientas OSC/REST para controlar o consultar el show.
3. **Plugins FFGL:** componentes opcionales para correcciones en tiempo real, como un deflicker temporal.

La primera implementación será sin interfaz gráfica. El núcleo deberá poder empaquetarse después como una aplicación portable para que colegas no tengan que instalar Python ni usar una consola.

## Opciones consideradas

### FFGL para todo

**Ventajas:** aparece dentro de Resolume y puede procesar frames en tiempo real.
**Desventajas:** no tiene acceso fiable al archivo fuente completo, no es apropiado para conversión DXV ni para diagnosticar proyector, PWM, tearing o cableado.

### Python externo para todo

**Ventajas:** acceso a archivos, FFprobe, FFmpeg, reportes y automatización.
**Desventajas:** inicialmente requiere una capa de distribución amigable para no exponer la consola.

### Arquitectura híbrida

**Ventajas:** cada problema se resuelve en el entorno correcto; permite reutilizar el núcleo en CLI, aplicación portable, web local o integración futura.
**Desventajas:** requiere definir contratos entre herramientas y mantener más de un tipo de componente.

## Consecuencias

- `RESOLUME_ADAPTER Diagnose` será la primera herramienta funcional.
- `RESOLUME_ADAPTER DXV Assistant` utilizará el encoder DXV disponible y comprobará sus capacidades antes de ejecutar.
- La conversión DXV deberá tener una alternativa explícita si el FFmpeg del usuario no incluye encoder DXV.
- Un futuro FFGL `Temporal Deflicker` no se presentará como detector universal de flicker.
- Los reportes deberán distinguir entre evidencia del archivo, hipótesis y pruebas externas pendientes.

## Acción siguiente

1. [ ] Validar el núcleo con clips sintéticos limpios, VFR, interlazados y con flicker conocido.
2. [ ] Añadir procesamiento por lotes.
3. [ ] Empaquetar el núcleo como aplicación portable para Windows.
4. [ ] Diseñar una presentación sin consola después de validar el flujo.
