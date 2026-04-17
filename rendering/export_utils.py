from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional


def build_export_manifest(
    *,
    format_name: str,
    source_markdown: Optional[str],
    output_file: str,
    engine: str,
    success: bool,
    note: str = "",
) -> Dict:
    return {
        "format": format_name,
        "source_markdown": source_markdown,
        "output_file": output_file,
        "engine": engine,
        "success": success,
        "note": note,
    }


def write_export_manifest(output_file: str, manifest: Dict) -> Path:
    suffix = Path(output_file).suffix or ".out"
    manifest_path = Path(output_file).with_suffix(f"{suffix}.export.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path
