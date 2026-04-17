from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .config import PipelineSettings
from .models import RunArtifacts, RunStats


def create_run_artifacts(settings: PipelineSettings) -> RunArtifacts:
    return RunArtifacts(
        run_id=uuid4().hex[:12],
        input_file=settings.input_file,
        started_at=datetime.now(timezone.utc),
        output_directory=settings.output_dir,
    )


def create_run_stats() -> RunStats:
    return RunStats()
