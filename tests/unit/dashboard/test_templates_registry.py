"""Unit tests for fenn.dashboard.templates_registry."""

import json

import pytest

from fenn.dashboard.templates_registry import TemplateEntry, TemplatesRegistry


def _entry(
    name: str,
    path,
    source_template: str = "base",
    pulled_at: str = "2026-07-21T10:00:00+00:00",
) -> TemplateEntry:
    return TemplateEntry(
        name=name,
        path=str(path),
        source_template=source_template,
        pulled_at=pulled_at,
    )


@pytest.fixture
def registry_path(tmp_path):
    return tmp_path / ".fenn" / "templates_registry.json"


@pytest.fixture
def registry(registry_path):
    return TemplatesRegistry(registry_path=registry_path)


class TestCreation:
    def test_list_templates_on_missing_file_returns_empty(self, registry):
        assert registry.list_templates() == []

    def test_add_or_update_creates_registry_file(
        self, tmp_path, registry, registry_path
    ):
        template_dir = tmp_path / "my_template"
        template_dir.mkdir()

        assert not registry_path.exists()
        registry.add_or_update(_entry("my_template", template_dir))

        assert registry_path.exists()

    def test_add_or_update_persists_all_fields(self, tmp_path, registry, registry_path):
        template_dir = tmp_path / "my_template"
        template_dir.mkdir()

        registry.add_or_update(
            _entry(
                "my_template",
                template_dir,
                source_template="vision",
                pulled_at="2026-07-21T12:34:56+00:00",
            )
        )

        [entry] = registry.list_templates()
        assert entry["name"] == "my_template"
        assert entry["path"] == str(template_dir.resolve())
        assert entry["source_template"] == "vision"
        assert entry["pulled_at"] == "2026-07-21T12:34:56+00:00"

    def test_add_or_update_keys_entries_by_resolved_path(
        self, tmp_path, registry, registry_path
    ):
        template_dir = tmp_path / "my_template"
        template_dir.mkdir()

        registry.add_or_update(_entry("my_template", template_dir))

        raw = json.loads(registry_path.read_text())
        assert list(raw.keys()) == [str(template_dir.resolve())]

    def test_registry_file_is_valid_json_on_disk(
        self, tmp_path, registry, registry_path
    ):
        template_dir = tmp_path / "my_template"
        template_dir.mkdir()
        registry.add_or_update(_entry("my_template", template_dir))

        # Should not raise.
        json.loads(registry_path.read_text())

    def test_corrupt_registry_file_is_tolerated(self, registry_path, registry):
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text("not valid json{{{")

        assert registry.list_templates() == []

    def test_non_dict_json_payload_is_tolerated(self, registry_path, registry):
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(json.dumps(["not", "a", "dict"]))

        assert registry.list_templates() == []

    def test_entries_missing_required_fields_are_dropped(self, registry_path, registry):
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps({"/some/path": {"name": "incomplete"}})  # missing fields
        )

        assert registry.list_templates() == []


class TestUpdates:
    def test_add_or_update_twice_with_same_path_does_not_duplicate(
        self, tmp_path, registry
    ):
        template_dir = tmp_path / "my_template"
        template_dir.mkdir()

        registry.add_or_update(
            _entry("my_template", template_dir, pulled_at="2026-07-20T00:00:00+00:00")
        )
        registry.add_or_update(
            _entry("my_template", template_dir, pulled_at="2026-07-21T00:00:00+00:00")
        )

        entries = registry.list_templates()
        assert len(entries) == 1

    def test_add_or_update_overwrites_fields_on_re_pull(self, tmp_path, registry):
        template_dir = tmp_path / "my_template"
        template_dir.mkdir()

        registry.add_or_update(
            _entry(
                "my_template",
                template_dir,
                source_template="base",
                pulled_at="2026-07-20T00:00:00+00:00",
            )
        )
        registry.add_or_update(
            _entry(
                "my_template",
                template_dir,
                source_template="base",
                pulled_at="2026-07-21T00:00:00+00:00",
            )
        )

        [entry] = registry.list_templates()
        assert entry["pulled_at"] == "2026-07-21T00:00:00+00:00"

    def test_multiple_distinct_templates_are_all_kept(self, tmp_path, registry):
        dir_a = tmp_path / "template_a"
        dir_b = tmp_path / "template_b"
        dir_a.mkdir()
        dir_b.mkdir()

        registry.add_or_update(
            _entry("template_a", dir_a, pulled_at="2026-07-20T00:00:00+00:00")
        )
        registry.add_or_update(
            _entry("template_b", dir_b, pulled_at="2026-07-21T00:00:00+00:00")
        )

        entries = registry.list_templates()
        assert {e["name"] for e in entries} == {"template_a", "template_b"}

    def test_list_templates_sorted_newest_pulled_first(self, tmp_path, registry):
        dir_a = tmp_path / "template_a"
        dir_b = tmp_path / "template_b"
        dir_a.mkdir()
        dir_b.mkdir()

        registry.add_or_update(
            _entry("template_a", dir_a, pulled_at="2026-07-20T00:00:00+00:00")
        )
        registry.add_or_update(
            _entry("template_b", dir_b, pulled_at="2026-07-21T00:00:00+00:00")
        )

        entries = registry.list_templates()
        assert [e["name"] for e in entries] == ["template_b", "template_a"]


class TestPruning:
    def test_deleted_template_directory_is_removed_from_list(self, tmp_path, registry):
        template_dir = tmp_path / "my_template"
        template_dir.mkdir()
        registry.add_or_update(_entry("my_template", template_dir))

        assert len(registry.list_templates()) == 1

        import shutil

        shutil.rmtree(template_dir)

        assert registry.list_templates() == []

    def test_pruned_entry_is_persisted_to_disk(self, tmp_path, registry, registry_path):
        template_dir = tmp_path / "my_template"
        template_dir.mkdir()
        registry.add_or_update(_entry("my_template", template_dir))

        import shutil

        shutil.rmtree(template_dir)
        registry.list_templates()  # triggers prune + save

        raw = json.loads(registry_path.read_text())
        assert raw == {}

    def test_pruning_only_removes_missing_entries_not_valid_ones(
        self, tmp_path, registry
    ):
        dir_a = tmp_path / "template_a"
        dir_b = tmp_path / "template_b"
        dir_a.mkdir()
        dir_b.mkdir()

        registry.add_or_update(_entry("template_a", dir_a))
        registry.add_or_update(_entry("template_b", dir_b))

        import shutil

        shutil.rmtree(dir_a)

        entries = registry.list_templates()
        assert [e["name"] for e in entries] == ["template_b"]

    def test_add_or_update_also_prunes_other_stale_entries(self, tmp_path, registry):
        dir_a = tmp_path / "template_a"
        dir_b = tmp_path / "template_b"
        dir_a.mkdir()
        dir_b.mkdir()

        registry.add_or_update(_entry("template_a", dir_a))

        import shutil

        shutil.rmtree(dir_a)

        # Adding a new, unrelated entry should also clean up the stale one.
        registry.add_or_update(_entry("template_b", dir_b))

        entries = registry.list_templates()
        assert [e["name"] for e in entries] == ["template_b"]

    def test_list_templates_write_failure_still_returns_pruned_view(
        self, tmp_path, registry, registry_path, monkeypatch
    ):
        template_dir = tmp_path / "my_template"
        template_dir.mkdir()
        registry.add_or_update(_entry("my_template", template_dir))

        import shutil

        shutil.rmtree(template_dir)

        def _boom(self, entries):
            raise OSError("disk full")

        monkeypatch.setattr(TemplatesRegistry, "_save_raw", _boom)

        # Should not raise even though persisting the prune fails.
        assert registry.list_templates() == []

    def test_existing_pytest_temp_entry_is_pruned_even_if_directory_exists(
        self, tmp_path, registry_path, registry
    ):
        pytest_temp_dir = (
            tmp_path
            / "pytest-of-user"
            / "pytest-123"
            / "test_pull_template_success0"
            / "downloaded-template"
        )
        pytest_temp_dir.mkdir(parents=True)

        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(
                {
                    str(pytest_temp_dir.resolve()): {
                        "name": "downloaded-template",
                        "path": str(pytest_temp_dir.resolve()),
                        "source_template": "base",
                        "pulled_at": "2026-07-21T10:00:00+00:00",
                    }
                }
            )
        )

        assert registry.list_templates() == []
        assert json.loads(registry_path.read_text()) == {}

    def test_add_or_update_ignores_pytest_temp_directory(
        self, tmp_path, registry, registry_path
    ):
        pytest_temp_dir = (
            tmp_path
            / "pytest-of-user"
            / "pytest-456"
            / "test_pull_template_success0"
            / "downloaded-template"
        )
        pytest_temp_dir.mkdir(parents=True)

        registry.add_or_update(_entry("downloaded-template", pytest_temp_dir))

        assert registry.list_templates() == []
        assert json.loads(registry_path.read_text()) == {}
