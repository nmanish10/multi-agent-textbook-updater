from __future__ import annotations

import shutil
from pathlib import Path


ASSET_ROOT = Path("outputs") / "extracted_assets"


def ensure_asset_dir(source_path: str) -> Path:
    destination = ASSET_ROOT / Path(source_path).stem
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def copy_local_asset(source_path: str, asset_reference: str, target_name: str | None = None) -> str:
    base_dir = Path(source_path).resolve().parent
    asset_path = (base_dir / asset_reference).resolve()
    if not asset_path.exists():
        return asset_reference

    destination_dir = ensure_asset_dir(source_path)
    target_file = _unique_destination(destination_dir / (target_name or asset_path.name))
    shutil.copy2(asset_path, target_file)
    return str(target_file.as_posix())


def write_binary_asset(source_path: str, filename: str, data: bytes) -> str:
    destination_dir = ensure_asset_dir(source_path)
    target_file = _unique_destination(destination_dir / filename)
    target_file.write_bytes(data)
    return str(target_file.as_posix())


def _unique_destination(target_file: Path) -> Path:
    if not target_file.exists():
        return target_file

    stem = target_file.stem
    suffix = target_file.suffix
    counter = 2
    while True:
        candidate = target_file.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1
