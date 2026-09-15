# ADR-015: Puente seguro de sesion NAYADE al contrato VJ

## Estado

Aceptado.

## Contexto

NAYADE registra una matriz de soundcheck y puede conservar una observacion
pasiva del procesador LED. Sin un puente, esos resultados no pueden entrar al
flujo comun de fases, checkpoints y replay. Copiar la sesion completa seria
innecesario y podria propagar notas, rutas o evidencia privada.

## Decision

`adapters/vj/nayade_input.py` construye un evento `preparation` de fuente
`NAYADE`. El evento conserva conteos y una lista acotada de resultados de
operador, ademas de datos tecnicos seleccionados de la observacion del
procesador: identidad declarada, transporte, confianza, senal, perfil de
modulo y los invariantes `read_only` y `commands_sent`.

El puente exige `read_only_source=true`, rechaza una observacion que declare
comandos enviados y requiere que el productor suministre `event_id` y
`sequence`. Las notas, textos de evidencia, rutas y campos desconocidos no
cruzan la frontera. El timestamp se toma de `updated_at` y debe incluir zona
horaria.

## Consecuencias

- NAYADE puede alimentar el estado VJ y un replay sin importar su modulo de
  soundcheck.
- El contrato conserva incertidumbre y observacion; no prueba por si solo el
  estado fisico del procesador o de la pantalla.
- El transporte del procesador se conserva como dato del payload, mientras la
  provenance del evento permanece `unknown` porque no se abrio ningun canal.
- No se ejecutan comandos, no se abren puertos y no se modifica mapping,
  Resolume ni hardware.

## Alternativas descartadas

- Copiar la sesion completa: expone datos innecesarios y privados.
- Tratar una observacion manual como lectura confirmada: confundiria evidencia
  del operador con estado verificado.
- Inferir la secuencia desde la cantidad de eventos: puede ocultar perdida o
  reordenamiento de eventos.
