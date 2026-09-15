# ADR-018: Integracion de las ramas VJ

## Estado

Aceptado en una rama de integracion aislada.

## Contexto

RESOLUME_ADAPTER tenia tres ramas de plugin independientes y una rama de adaptador VJ.
INSTAR ya contenia la implementacion mas completa del flujo de medios,
mapping, tarjeta de prueba, procesadores y soundcheck. NAYADE e IMAGO tambien
tenian ramas propias, pero NAYADE incluia una segunda implementacion reducida
de la sesion de soundcheck.

## Decision

La rama `codex/resolume_adapter-vj-integration` se construye desde `main` en este orden:

1. INSTAR como base funcional de herramientas VJ.
2. NAYADE e IMAGO como capacidades que no duplican la base existente.
3. El adaptador VJ y sus puentes host-neutrales desde
   `codex/resolume_adapter-lucida-plugin-replay`.

Cuando hubo conflicto entre las dos implementaciones NAYADE, se conservo la
de INSTAR porque soporta catalogo, adaptacion target-specific, matriz de
soundcheck, tarjeta de prueba y procesadores. Se excluyo el test que solo
ejercitaba la implementacion duplicada. La capacidad de IMAGO se integro en la
CLI completa de INSTAR mediante el comando `imago-session`.

## Consecuencias

- La rama integrada ofrece una superficie CLI unica y conserva las
  responsabilidades INSTAR, NAYADE e IMAGO.
- Los puentes VJ siguen separados del codigo concreto de las herramientas y
  se mantienen proposal-only y read-only.
- Las ramas originales no se reescriben ni se fusionan automaticamente a
  `main`; esta rama requiere revision antes de cualquier merge posterior.
- El resultado actual pasa la suite completa, el grafo de schemas y el guard
  de ASCII.

## Limites

Esta integracion no conecta Resolume, procesadores LED, DMX, sockets, GPU,
MCP ni datos de venues. Tampoco valida el estado fisico de una pantalla.
