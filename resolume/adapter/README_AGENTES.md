# RESOLUME_ADAPTER — mapa de trabajo para agentes

`main` es la integración estable del producto. Las ramas `agent/*` son
contextos de enfoque: ayudan a iniciar una tarea con el lenguaje, las rutas,
los riesgos y las comprobaciones adecuadas, pero no son silos ni sustituyen la
revisión de cambios.

## Flujo recomendado

1. Elige el contexto de `agent/instar`, `agent/nayade`, `agent/imago`,
   `agent/lucida` o `agent/vj-adapter`.
2. Para un encargo concreto, crea una rama corta desde ese contexto, por
   ejemplo `agent/lucida/validate-overlay-replay`.
3. Deja el trabajo acotado a una intención y abre un Pull Request hacia
   `main`. Si cruza dominios, explica la frontera y pide las revisiones que
   correspondan.
4. Ejecuta las pruebas relevantes y la suite completa cuando el cambio afecte
   contratos compartidos, CLI o integración.
5. Fusiona sólo después de revisar evidencia, compatibilidad y riesgos. Borra
   la rama corta cuando el PR termine; conserva tags o commits si necesitas
   marcar un hito.

## Principios para agentes

- Decide los detalles reversibles y pregunta sólo cuando falte una decisión de
  significado, autoridad o consecuencias.
- Usa las herramientas y la profundidad que resuelvan el encargo; estas guías
  son contexto, no una lista de pasos obligatorios.
- Distingue hechos, cálculos, hipótesis, propuestas y acciones ejecutadas.
- Conserva incertidumbre y procedencia cuando sean parte de la decisión.
- Añade límites sólo cuando protejan una frontera real; si el encargo cambia
  el alcance, analiza el nuevo riesgo en vez de bloquearlo por reflejo.

## Contextos disponibles

| Rama | Documento | Enfoque |
|---|---|---|
| [`agent/instar`](https://github.com/ligereza/resolume_adapter/tree/agent/instar) | `README_AGENTES_INSTAR.md` | Media, preflight, DXV, CUES, mapping y adaptaciones. |
| [`agent/nayade`](https://github.com/ligereza/resolume_adapter/tree/agent/nayade) | `README_AGENTES_NAYADE.md` | Soundcheck, procesadores LED, señal, color y geometría. |
| [`agent/imago`](https://github.com/ligereza/resolume_adapter/tree/agent/imago) | `README_AGENTES_IMAGO.md` | Show, estado, incidentes, recovery y cierre. |
| [`agent/lucida`](https://github.com/ligereza/resolume_adapter/tree/agent/lucida) | `README_AGENTES_LUCIDA.md` | Contratos, schemas, señales, overlays, replay y host boundaries. |
| [`agent/vj-adapter`](https://github.com/ligereza/resolume_adapter/tree/agent/vj-adapter) | `README_AGENTES_VJ_ADAPTER.md` | Puentes VJ, proyecciones acotadas y replay host-neutral. |

Cada contexto incluye además un perfil `.github/agents/*.agent.md` y una
instrucción `.github/instructions/*.instructions.md` con alcance por rutas.
Adáptalos cuando una necesidad recurrente aparezca; no los conviertas en
reglas generales a partir de un solo caso.
