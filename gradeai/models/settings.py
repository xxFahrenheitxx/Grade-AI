"""Application settings model."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from gradeai.constants import (
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROVIDER,
    DEFAULT_THEME,
    MAX_RECENT_PROJECTS,
)


def _settings_path() -> Path:
    """Return the path to the settings file."""
    config_dir = Path.home() / ".gradeai"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "settings.json"


@dataclass
class AppSettings:
    """Global application settings persisted to disk."""

    api_key: str = ""
    ai_provider: str = DEFAULT_AI_PROVIDER
    ai_model: str = DEFAULT_AI_MODEL
    theme: str = DEFAULT_THEME
    recent_projects: list[str] = field(default_factory=list)
    window_geometry: Optional[str] = None
    window_state: Optional[str] = None
    splitter_sizes: Optional[list[int]] = None
    # Per-project UI state (keyed by project path)
    project_ui_states: dict[str, dict] = field(default_factory=dict)

    def add_recent_project(self, path: str) -> None:
        """Add a project path to the recent list (most recent first)."""
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        self.recent_projects = self.recent_projects[:MAX_RECENT_PROJECTS]

    def save(self) -> None:
        """Persist settings to disk."""
        data = {
            "api_key": self.api_key,
            "ai_provider": self.ai_provider,
            "ai_model": self.ai_model,
            "theme": self.theme,
            "recent_projects": self.recent_projects,
            "window_geometry": self.window_geometry,
            "window_state": self.window_state,
            "splitter_sizes": self.splitter_sizes,
            "project_ui_states": self.project_ui_states,
        }
        path = _settings_path()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> AppSettings:
        """Load settings from disk, or return defaults."""
        path = _settings_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                api_key=data.get("api_key", ""),
                ai_provider=data.get("ai_provider", DEFAULT_AI_PROVIDER),
                ai_model=data.get("ai_model", DEFAULT_AI_MODEL),
                theme=data.get("theme", DEFAULT_THEME),
                recent_projects=data.get("recent_projects", []),
                window_geometry=data.get("window_geometry"),
                window_state=data.get("window_state"),
                splitter_sizes=data.get("splitter_sizes"),
                project_ui_states=data.get("project_ui_states", {}),
            )
        except (json.JSONDecodeError, KeyError):
            return cls()
