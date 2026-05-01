from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _stringify_prompt_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


@lru_cache(maxsize=None)
def load_prompt_definition(name: str) -> dict[str, Any]:
    path = PROMPT_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt definition not found for '{name}': {path}")

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Prompt definition for '{name}' must be a mapping")
    return payload


def prompt_version(name: str) -> str:
    definition = load_prompt_definition(name)
    return str(definition.get("version", "unversioned"))


def prompt_system(name: str, default: str | None = None) -> str | None:
    definition = load_prompt_definition(name)
    system_prompt = definition.get("system_prompt")
    if system_prompt is None:
        return default
    return str(system_prompt)


def prompt_template(name: str) -> str:
    definition = load_prompt_definition(name)
    template = definition.get("user_prompt")
    if not template:
        raise ValueError(f"Prompt definition for '{name}' is missing user_prompt")
    return str(template)


def render_prompt(name: str, **values: Any) -> str:
    template = prompt_template(name)
    normalized = {key: _stringify_prompt_value(value) for key, value in values.items()}
    return template.format(**normalized).strip() + "\n"
