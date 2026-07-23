"""Stable RC2 façade for USANDO workspace and AutoPPTX release planning."""
from .autopptx_workspace import (
    AutoPPTXPipelineError,
    build_usando_update_plan,
    canonical_digest,
    create_project_workspace,
    natural_key,
    validate_project_code,
)
from .autopptx_release_plan import (
    build_autopptx_pipeline_plan,
    stage_autopptx_media,
)

__all__ = [
    "AutoPPTXPipelineError",
    "build_autopptx_pipeline_plan",
    "build_usando_update_plan",
    "canonical_digest",
    "create_project_workspace",
    "natural_key",
    "stage_autopptx_media",
    "validate_project_code",
]
