# ADR-001: Repositorio local y documentación operativa como base

**Estado:** Aceptado  
**Fecha:** 2026-08-28  
**Decisor:** Propietario del equipo VJ

## Contexto

El trabajo VJ combina decisiones técnicas y operativas: preparación de medios, reproducción,
salida de video, temperatura, rendimiento y resolución de incidentes. Parte del conocimiento
se pierde porque queda en conversaciones, capturas o pruebas aisladas.

El repositorio debe ser útil con poca preparación, funcionar sin servicios externos y no
convertirse en un lugar para almacenar archivos de video pesados.

## Decisión

Usaremos Markdown para conocimiento y runbooks, PowerShell para comprobaciones locales de
Windows y Git para el historial. Los medios, renders y capturas de diagnóstico se mantendrán
fuera del control de versiones salvo decisión explícita.

Cada caso nuevo deberá distinguir:

- **Observado:** dato medido o reproducible.
- **Hipótesis:** explicación todavía no confirmada.
- **Acción:** cambio aplicado o prueba ejecutada.
- **Resultado:** evidencia posterior y siguiente paso.

## Opciones consideradas

### Manual único

**Ventajas:** rápido de comenzar.  
**Desventajas:** difícil de navegar, mezcla procedimientos y contexto, y crece sin estructura.

### Aplicación o base de datos desde el inicio

**Ventajas:** permite formularios y búsquedas más avanzadas.  
**Desventajas:** añade mantenimiento y dependencias antes de conocer el flujo real.

### Repositorio modular de Markdown y scripts — elegido

**Ventajas:** portable, auditable, fácil de versionar y suficiente para el show inmediato.  
**Desventajas:** la búsqueda y la captura de datos son menos automáticas al principio.

## Consecuencias

- Se puede consultar un procedimiento desde cualquier copia del repositorio.
- Las herramientas pueden ejecutarse sin modificar el equipo.
- Las conclusiones térmicas y de rendimiento quedarán asociadas a evidencia.
- Más adelante se podrá añadir una interfaz o base de datos sin perder la documentación base.

## Acciones

- [x] Crear estructura inicial de documentación.
- [x] Crear verificación previa al show.
- [x] Crear captura de estado del sistema.
- [ ] Añadir inventario técnico de clips.
- [ ] Añadir registro de casos e incidentes.

