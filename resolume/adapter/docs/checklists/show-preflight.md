# Checklist: preflight de show VJ

## Equipo

- [ ] Portátil conectado a corriente.
- [ ] Ventilación libre; equipo sobre una superficie rígida.
- [ ] Perfil de energía revisado y conocido.
- [ ] Resolume abre sin errores.
- [ ] GPU y pantalla/proyector aparecen correctamente.
- [ ] Aplicaciones de render y sincronización innecesarias están cerradas.

## Proyecto y medios

- [ ] Proyecto guardado en su ubicación definitiva.
- [ ] Medios DXV ubicados en el SSD elegido.
- [ ] No hay clips offline.
- [ ] Se probó un loop representativo en la composición real.
- [ ] FPS, resolución, progresivo y alpha son los esperados.
- [ ] Existe una copia de seguridad del proyecto y de los archivos esenciales.

## Prueba de reproducción

- [ ] El loop funciona durante varios minutos.
- [ ] No hay flicker visible en el archivo.
- [ ] No hay tearing en la salida.
- [ ] La salida usa la frecuencia de refresco prevista.
- [ ] Se anotaron observaciones y cualquier limitación conocida.

## Comandos opcionales

```powershell
.\tools\Test-VJPreflight.ps1 -MediaRoot "D:\VJ\Media" -ProjectRoot "D:\VJ\Shows\show-01"
.\tools\Get-VJSystemSnapshot.ps1 -OutputPath ".\artifacts\show-01-before.json"
```

