"""Planes de investigación segura para incidentes VJ."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


INCIDENT_CATEGORIES = (
    "flicker",
    "tearing",
    "frames_dropped",
    "lost_media",
    "gray_black_levels",
    "geometry_scaling",
    "signal_loss",
)
INCIDENT_STAGES = ("preflight", "soundcheck", "show")

_CATALOG: dict[str, dict[str, Any]] = {
    "flicker": {
        "title": "Parpadeo o luminancia inestable",
        "severity": "high",
        "evidence": [
            "¿El parpadeo está en el archivo, en la preview o sólo en la pantalla física?",
            "¿La frecuencia de salida, la del procesador y la de la pantalla coinciden?",
            "¿Aparece con un color sólido, con movimiento o sólo con estrobo?",
        ],
        "hypotheses": [
            ("source_content", "El parpadeo está presente en el medio original o en su cadencia."),
            ("refresh_chain", "Hay una incompatibilidad de frecuencia o sincronía en la cadena de salida."),
            ("led_pwm", "El comportamiento PWM o la electrónica del LED reacciona al contenido."),
        ],
        "actions": [
            ("freeze_source", "freeze_current_visual", "Congelar la visual estable evita introducir otra variable."),
            ("compare_testcard", "show_solid_and_motion_patterns", "Comparar patrón sólido, grilla y movimiento separa contenido de cadena."),
            ("record_chain", "record_refresh_and_signal_evidence", "Registrar valores observados permite repetir la comprobación sin tocar ajustes."),
        ],
        "recovery": ["Volver a la visual estable", "Confirmar que el operador conserva el preset actual", "Repetir el patrón de prueba y registrar si el síntoma desapareció"],
    },
    "tearing": {
        "title": "Cortes horizontales o tearing",
        "severity": "medium",
        "evidence": [
            "¿El corte se desplaza horizontalmente mientras la imagen se mueve?",
            "¿Aparece también en una captura local o sólo en la salida física?",
            "¿El FPS de composición y la frecuencia de salida son estables?",
        ],
        "hypotheses": [
            ("sync_mismatch", "La salida no está presentando los frames con sincronía estable."),
            ("capture_path", "La captura o conversión intermedia introduce el corte."),
            ("source_interlace", "El material tiene campos entrelazados o una cadencia incompatible."),
        ],
        "actions": [
            ("hold_motion", "hold_motion_testcard", "Una línea móvil permite distinguir tearing de parpadeo."),
            ("record_output", "record_output_timing", "Registrar FPS y Hz evita corregir a ciegas."),
            ("use_stable_source", "switch_to_known_stable_clip", "Un clip estable sirve como control sin modificar el mapping."),
        ],
        "recovery": ["Mantener el clip de control si es necesario", "No cambiar simultáneamente FPS y mapping", "Verificar la salida después de cada cambio aprobado"],
    },
    "frames_dropped": {
        "title": "Frames dropped o reproducción entrecortada",
        "severity": "medium",
        "evidence": [
            "¿El contador cae en Resolume, en el preview o sólo en la pantalla?",
            "¿El clip es DXV, tiene alpha, resolución extrema o demasiadas capas simultáneas?",
            "¿CPU, GPU, VRAM y disco muestran saturación al mismo tiempo?",
        ],
        "hypotheses": [
            ("decode_load", "El codec o la complejidad de decodificación supera el margen disponible."),
            ("render_load", "La composición, efectos o resolución saturan el render."),
            ("storage_load", "El almacenamiento o la ruta de red no entrega datos a tiempo."),
        ],
        "actions": [
            ("reduce_scope", "isolate_one_clip_and_layer", "Aislar la carga evita culpar al clip equivocado."),
            ("prefer_local_dvx", "use_local_dxv_derivative", "Una copia DXV local ofrece una comparación reproducible."),
            ("record_resource_snapshot", "record_cpu_gpu_vram_and_disk", "El snapshot permite comparar sin intervenir en el show."),
        ],
        "recovery": ["Volver a la composición estable", "Reducir capas sólo con aprobación explícita", "Conservar el clip original y la derivada como pares comparables"],
    },
    "lost_media": {
        "title": "Media ausente o ruta perdida",
        "severity": "high",
        "evidence": [
            "¿La ruta falta sólo en el equipo actual o también en el almacenamiento original?",
            "¿Existe una copia DXV con el mismo nombre y huella?",
            "¿El showfile apunta a una carpeta movida, a una unidad diferente o a una ruta de red?",
        ],
        "hypotheses": [
            ("relocation", "El medio fue movido y la composición conserva una ruta antigua."),
            ("drive_unavailable", "La unidad o volumen no está montado o cambió de letra."),
            ("missing_derivative", "Existe el original, pero no la derivada DXV esperada."),
        ],
        "actions": [
            ("inventory_candidates", "inventory_matching_media", "Listar candidatos es reversible y no modifica el showfile."),
            ("preserve_source", "preserve_original_and_derivative", "Conservar ambas versiones permite volver atrás."),
            ("propose_relocate", "propose_relocate_on_copy", "La relocalización sólo se propone sobre una copia aprobada."),
        ],
        "recovery": ["No sobrescribir la composición original", "Probar la ruta en una copia", "Confirmar cada media relocalizada antes del show"],
    },
    "gray_black_levels": {
        "title": "Negro gris, rango o gamma incorrectos",
        "severity": "high",
        "evidence": [
            "¿El gris aparece en negro absoluto, PLUGE, visuales y una fuente externa?",
            "¿La GPU está en rango completo o limitado y qué declara el procesador?",
            "¿El síntoma cambia al cruzar otra entrada sin modificar el procesador?",
        ],
        "hypotheses": [
            ("range_mismatch", "La cadena mezcla niveles limitados y completos."),
            ("processor_calibration", "El procesador aplica una curva, gamma o black level inesperada."),
            ("panel_behavior", "El módulo o su configuración física limita el negro percibido."),
        ],
        "actions": [
            ("run_pluge", "run_pluge_and_gray_ramp", "PLUGE y rampa de grises aportan evidencia comparable."),
            ("snapshot_processor", "capture_processor_read_only_snapshot", "Leer y guardar la configuración evita ajustes al ojo."),
            ("compare_known_source", "compare_known_reference_source", "Una fuente de referencia ayuda a localizar la primera divergencia."),
        ],
        "recovery": ["Conservar el preset actual antes de cualquier cambio", "Volver a la fuente estable", "Escalar al operador si la configuración no está documentada"],
    },
    "geometry_scaling": {
        "title": "Deformación, crop o escalado incorrecto",
        "severity": "medium",
        "evidence": [
            "¿Un círculo aparece ovalado en toda la salida o sólo en una slice?",
            "¿InputRect y OutputRect mantienen la misma proporción?",
            "¿La visual está siendo fit, crop, stretch o warpeada por el mapping?",
        ],
        "hypotheses": [
            ("mapping_aspect", "InputRect y OutputRect tienen escalas no uniformes."),
            ("processor_scaling", "El procesador vuelve a escalar una señal ya mapeada."),
            ("content_mismatch", "El contenido fue diseñado para otra proporción y el crop oculta la evidencia."),
        ],
        "actions": [
            ("run_geometry_card", "run_geometry_testcard", "Círculo, cuadrado y línea móvil separan deformación de contenido."),
            ("compare_fit_crop", "preview_fit_and_crop_variants", "Comparar variantes conserva proporción y evita stretch automático."),
            ("inspect_mapping", "inspect_input_output_and_warp", "Leer el mapping identifica la primera transformación sospechosa."),
        ],
        "recovery": ["Volver a la última variante sin deformación", "No aplicar stretch como corrección silenciosa", "Confirmar la tarjeta en la salida real"],
    },
    "signal_loss": {
        "title": "Pérdida de señal o pantalla incompleta",
        "severity": "high",
        "evidence": [
            "¿Falla toda la salida, una pantalla, una slice o sólo una cadena física?",
            "¿El sistema operativo conserva el display y el EDID?",
            "¿El preset muestra todas las salidas que el operador realmente conectó?",
        ],
        "hypotheses": [
            ("routing", "El operador o la consola capturó sólo parte de la salida."),
            ("cable_or_converter", "HDMI, conversor o enlace intermedio pierde sincronía."),
            ("processor_port", "Un puerto o salida del procesador está desconectado o limitado."),
        ],
        "actions": [
            ("probe_output", "probe_windows_output_and_edid", "La sonda de salida registra lo que el equipo declara sin cambiarlo."),
            ("compare_mapping", "compare_mapping_with_physical_route", "Comparar XML y ruta física detecta pantallas omitidas."),
            ("test_single_route", "test_single_known_route", "Una ruta mínima separa fallo de fuente y distribución."),
        ],
        "recovery": ["Mantener la salida conocida estable", "No cambiar puertos del procesador sin backup", "Registrar qué pantallas sí fueron entregadas"],
    },
}


def build_incident_plan(category: str, *, stage: str = "soundcheck") -> dict[str, Any]:
    """Genera un plan de evidencia y recuperación sin ejecutar ninguna acción."""

    normalized = category.strip().lower() if isinstance(category, str) else ""
    if normalized not in INCIDENT_CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(INCIDENT_CATEGORIES)}")
    if not isinstance(stage, str) or stage.strip().lower() not in INCIDENT_STAGES:
        raise ValueError(f"stage must be one of: {', '.join(INCIDENT_STAGES)}")
    definition = _CATALOG[normalized]
    hypotheses = [
        {"id": identifier, "statement": statement, "status": "possible"}
        for identifier, statement in definition["hypotheses"]
    ]
    actions = [
        {
            "action_id": action_id,
            "operation": operation,
            "reason": reason,
            "requires_confirmation": True,
            "reversible": True,
            "execution_mode": "proposal_only",
        }
        for action_id, operation, reason in definition["actions"]
    ]
    return {
        "schema_version": "0.1",
        "plan_type": "ResolumeAdapterIncidentPlan",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "category": normalized,
        "stage": stage.strip().lower(),
        "title": definition["title"],
        "severity": definition["severity"],
        "evidence_questions": [
            {"question_id": f"evidence-{index:02d}", "question": question}
            for index, question in enumerate(definition["evidence"], start=1)
        ],
        "hypotheses": hypotheses,
        "proposals": actions,
        "recovery_checklist": definition["recovery"],
        "safety": {
            "read_only": True,
            "hardware_changed": False,
            "showfile_changed": False,
            "automatic_execution": False,
        },
        "limitations": [
            "Un plan no confirma por sí solo la causa del síntoma.",
            "La observación de la pantalla física y del operador sigue siendo necesaria.",
            "Las propuestas deben registrarse y aprobarse explícitamente antes de probarlas.",
        ],
    }


def incident_text_report(plan: Mapping[str, Any]) -> str:
    lines = [
        "RESOLUME_ADAPTER INCIDENT PLAN",
        "====================",
        f"Categoría: {plan['category']}",
        f"Etapa: {plan['stage']}",
        f"Severidad orientativa: {plan['severity']}",
        f"Título: {plan['title']}",
        "",
        "Evidencia a capturar:",
    ]
    lines.extend(f"  {item['question_id']}. {item['question']}" for item in plan["evidence_questions"])
    lines.extend(["", "Hipótesis:"])
    lines.extend(f"  [{item['status']}] {item['id']}: {item['statement']}" for item in plan["hypotheses"])
    lines.extend(["", "Propuestas:"])
    lines.extend(f"  {item['action_id']}: {item['operation']} (requiere aprobación)" for item in plan["proposals"])
    lines.append("\nModo: propuesta_only; no se modificó showfile ni hardware.")
    return "\n".join(lines)


def write_incident_plan(plan: Mapping[str, Any], path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(plan), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


__all__ = ["INCIDENT_CATEGORIES", "INCIDENT_STAGES", "build_incident_plan", "incident_text_report", "write_incident_plan"]
