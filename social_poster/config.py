"""Configuration loading.

Config is a small JSON (or YAML, if PyYAML is installed) document::

    {
      "database": "posts.db",
      "platforms": {
        "mastodon": {"api_base_url": "https://mastodon.social"},
        "twitter":  {}
      }
    }

Secrets (tokens) are intentionally *not* required in the file — adapters fall
back to environment variables so credentials stay out of version control.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    database: str = "posts.db"
    platforms: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        data = _parse(text, path.suffix.lower())
        if not isinstance(data, dict):
            raise ValueError(f"Config root must be an object, got {type(data).__name__}")
        return cls(
            database=data.get("database", "posts.db"),
            platforms=data.get("platforms", {}) or {},
        )


def _parse(text: str, suffix: str) -> object:
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # noqa: PLC0415 (optional dependency)
        except ImportError as exc:
            raise RuntimeError(
                "YAML config requires PyYAML (pip install pyyaml), "
                "or use a .json config file"
            ) from exc
        return yaml.safe_load(text)
    return json.loads(text)
