"""Reusable VJ adapter for the VJ interface layer.

The adapter is deliberately side-effect free: it consumes events and states,
returns proposals, and records results. It never talks to a live show by
itself.
"""

from .adapter import VJAdapter, VJAdapterError
from .contracts import VJEvent, VJResult, VJState, VJProposal
from .semantic_light_field import (
    SemanticLightFieldBridgeError,
    adapt_semantic_light_field,
    resolve_semantic_light_field_tape,
)
from .instar_input import (
    InstarInputError,
    InstarInputProjector,
    build_instar_event,
    project_instar_show_input,
)
from .nayade_input import (
    NayadeInputError,
    NayadeInputProjector,
    build_nayade_event,
    project_nayade_show_input,
)
from .imago_input import (
    ImagoInputError,
    ImagoInputProjector,
    build_imago_event,
    project_imago_show_input,
)
from .project import (
    PROJECT_STAGES,
    VJProjectError,
    build_stage_event,
    load_project_document,
    project_stage_document,
)
from .show_input import (
    ShowInputError,
    ShowInputProjection,
    ShowInputProjector,
    StaleShowInputError,
    project_show_input,
    project_osc_show_input,
    validate_show_input,
)
from .console_proposals import (
    ConsoleProposalError,
    build_console_proposals,
)

__all__ = [
    "VJAdapter",
    "VJAdapterError",
    "VJEvent",
    "VJResult",
    "VJState",
    "VJProposal",
    "SemanticLightFieldBridgeError",
    "adapt_semantic_light_field",
    "resolve_semantic_light_field_tape",
    "InstarInputError",
    "InstarInputProjector",
    "build_instar_event",
    "project_instar_show_input",
    "NayadeInputError",
    "NayadeInputProjector",
    "build_nayade_event",
    "project_nayade_show_input",
    "ImagoInputError",
    "ImagoInputProjector",
    "build_imago_event",
    "project_imago_show_input",
    "PROJECT_STAGES",
    "VJProjectError",
    "build_stage_event",
    "load_project_document",
    "project_stage_document",
    "ShowInputError",
    "ShowInputProjection",
    "ShowInputProjector",
    "StaleShowInputError",
    "project_show_input",
    "project_osc_show_input",
    "validate_show_input",
    "ConsoleProposalError",
    "build_console_proposals",
]
