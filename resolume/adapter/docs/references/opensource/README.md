# Referencias open source descargadas

Estas copias locales se usan para estudiar protocolos y límites de comunicación. No se ejecutan como parte de RESOLUME_ADAPTER ni habilitan escrituras automáticas.

- `novastar/`: https://github.com/sarakusha/novastar
- `colorlight/`: https://github.com/haraldkubota/colorlight

Las carpetas están ignoradas por Git porque son dependencias externas de referencia. Si se eliminan, se pueden recuperar con:

```powershell
git clone --depth 1 https://github.com/sarakusha/novastar docs/references/opensource/novastar
git clone --depth 1 https://github.com/haraldkubota/colorlight docs/references/opensource/colorlight
```

La implementación de NAYADE debe tomar de estos proyectos únicamente ideas verificadas contra el modelo, firmware y documentación oficial del procesador real.
