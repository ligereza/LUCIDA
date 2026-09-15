# RESOLUME_ADAPTER portable para colegas

Este flujo instala el entorno Python local de RESOLUME_ADAPTER y permite ejecutar sus
comandos desde PowerShell sin conocer las rutas internas del repositorio.

## Preparar una copia

1. Clona o copia el repositorio en una carpeta local.
2. Abre PowerShell en cualquier ubicación.
3. Ejecuta el bootstrap usando la ruta completa del repositorio:

```powershell
& "C:\Ruta\RESOLUME_ADAPTER\tools\Bootstrap-RESOLUME_ADAPTER.ps1" -Dev
```

El script crea `.venv` dentro del repositorio y usa `requirements.txt`. `-Dev`
agrega las herramientas de prueba. Para el backend NVIDIA opcional:

```powershell
& "C:\Ruta\RESOLUME_ADAPTER\tools\Bootstrap-RESOLUME_ADAPTER.ps1" -Gpu
```

No se instala nada fuera del entorno `.venv` salvo los componentes que Python
requiera para crear ese entorno. La carpeta `.venv` está ignorada por Git.

## Ejecutar la CLI desde cualquier carpeta

```powershell
& "C:\Ruta\RESOLUME_ADAPTER\tools\Invoke-RESOLUME_ADAPTER.ps1" --help
& "C:\Ruta\RESOLUME_ADAPTER\tools\Invoke-RESOLUME_ADAPTER.ps1" instar "D:\VJ\Media" --report "D:\VJ\Reports\instar.json"
```

El launcher prefiere `.venv\Scripts\python.exe`. Si todavía no existe, usa el
`python` disponible en `PATH` y muestra un error accionable si no encuentra
Python.

Antes de un show, se puede comprobar la copia portable y sus dependencias sin
abrir Resolume ni tocar hardware:

```powershell
& "C:\Ruta\RESOLUME_ADAPTER\tools\Invoke-RESOLUME_ADAPTER.ps1" doctor --report "D:\VJ\Reports\doctor.json"
```

`PASS` confirma el entorno base; `WARN` indica capacidades opcionales o
herramientas externas ausentes; `FAIL` requiere corregir el entorno antes de
usar la función afectada.

Para un incidente durante soundcheck o show, se puede generar una guía
acotada sin modificar el showfile:

```powershell
& "C:\Ruta\RESOLUME_ADAPTER\tools\Invoke-RESOLUME_ADAPTER.ps1" incident-plan gray_black_levels --stage soundcheck
& "C:\Ruta\RESOLUME_ADAPTER\tools\Invoke-RESOLUME_ADAPTER.ps1" incident-plan flicker --stage show --report "D:\VJ\Reports\flicker-plan.json"
```

El plan separa preguntas de evidencia, hipótesis y propuestas de recuperación.
Todas las propuestas requieren aprobación explícita y son `proposal_only`.

## Límites de seguridad

- La CLI sólo cambia archivos cuando el comando recibe explícitamente una ruta
  de salida.
- Los comandos de Resolume, mapping y procesadores permanecen en modo lectura
  o propuesta.
- El bootstrap instala dependencias; no cambia BIOS, drivers, perfil de
  energía, Resolume ni configuraciones del procesador LED.
- Los medios pesados y los reportes locales deben mantenerse fuera del commit.

## Comprobación rápida

```powershell
& "C:\Ruta\RESOLUME_ADAPTER\tools\Invoke-RESOLUME_ADAPTER.ps1" vj-replay `
  "C:\Ruta\RESOLUME_ADAPTER\adapters\vj\replay\fixtures\plugin-bridges-fictional.json"
```

La respuesta esperada termina con `PASS`. Este replay es sintético y no abre
puertos ni ejecuta propuestas.
