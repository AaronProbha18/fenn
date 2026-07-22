"""Local registry of templates downloaded via `fenn pull`."""

import json
import os
import re
from pathlib import Path

from fenn.dashboard.types import TemplateEntry

_DEFAULT_REGISTRY_PATH = "~/.fenn/templates_registry.json"


def _default_registry_path() -> Path:
    """Resolve the registry path, honoring FENN_TEMPLATES_REGISTRY_PATH.

    Returns:
        The path to the local templates registry file.
    """
    return Path(
        os.environ.get("FENN_TEMPLATES_REGISTRY_PATH", _DEFAULT_REGISTRY_PATH)
    ).expanduser()


def _is_pytest_temp_path(path: Path) -> bool:
    """Return whether a path looks like a pytest pull-template artifact."""
    lowered_parts = [part.lower() for part in path.parts]
    has_pytest_root = any(part.startswith("pytest-of-") for part in lowered_parts)
    has_pytest_run = any(re.fullmatch(r"pytest-\d+", part) for part in lowered_parts)
    has_pull_test = any(part.startswith("test_pull_template") for part in lowered_parts)
    return has_pytest_root and has_pytest_run and has_pull_test


class TemplatesRegistry:
    """Reads and writes the local template registry."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self._path = registry_path or _default_registry_path()

    # ------------------------------------------------------------------
    # Internal load/save helpers
    # ------------------------------------------------------------------

    def _load_raw(self) -> dict[str, TemplateEntry]:
        """Load and validate the registry file, tolerating missing/corrupt data.

        Returns:
            The raw registry entries as a dictionary keyed by template path.
        """
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return {}

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}

        if not isinstance(payload, dict):
            return {}

        cleaned: dict[str, TemplateEntry] = {}
        for key, entry in payload.items():
            if not isinstance(key, str) or not isinstance(entry, dict):
                continue
            name = entry.get("name")
            path = entry.get("path")
            source_template = entry.get("source_template")
            pulled_at = entry.get("pulled_at")
            if not all(
                isinstance(v, str) and v
                for v in (name, path, source_template, pulled_at)
            ):
                continue
            cleaned[key] = TemplateEntry(
                name=name,
                path=path,
                source_template=source_template,
                pulled_at=pulled_at,
            )
        return cleaned

    def _save_raw(self, entries: dict[str, TemplateEntry]) -> None:
        """Persist the registry atomically.

        Args:
            entries: The registry entries to save.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(entries, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(tmp_path, self._path)

    @staticmethod
    def _prune_missing(
        entries: dict[str, TemplateEntry],
    ) -> tuple[dict[str, TemplateEntry], bool]:
        """Drop entries that are stale or point to pytest temp directories.

        Args:
            entries: The registry entries to prune.

        Returns:
            A tuple containing the pruned entries and a boolean indicating if any entries were removed.
        """
        pruned: dict[str, TemplateEntry] = {}
        changed = False
        for key, entry in entries.items():
            entry_path = Path(entry["path"])
            if _is_pytest_temp_path(entry_path):
                changed = True
                continue
            if entry_path.exists():
                pruned[key] = entry
            else:
                changed = True
        return pruned, changed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_templates(self) -> list[TemplateEntry]:
        """Return all registered templates, most recently pulled first.

        Returns:
            A list of all registered templates, most recently pulled first.
        """
        entries = self._load_raw()
        pruned, changed = self._prune_missing(entries)
        if changed:
            try:
                self._save_raw(pruned)
            except OSError:
                pass
        return sorted(pruned.values(), key=lambda e: e["pulled_at"], reverse=True)

    def add_or_update(self, entry: TemplateEntry) -> None:
        """Add or update a registry entry, keyed by its resolved absolute path.

        Args:
            entry: The template entry to add or update.
        """
        entries = self._load_raw()
        entries, _ = self._prune_missing(entries)

        resolved_path = str(Path(entry["path"]).resolve())
        if _is_pytest_temp_path(Path(resolved_path)):
            self._save_raw(entries)
            return

        entries[resolved_path] = TemplateEntry(
            name=entry["name"],
            path=resolved_path,
            source_template=entry["source_template"],
            pulled_at=entry["pulled_at"],
        )
        self._save_raw(entries)
