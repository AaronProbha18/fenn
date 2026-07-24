"""Tests for fenn/cli/run.py"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from fenn.cli.run import (
    DEFAULT_SCRIPT,
    TERMINAL_STATUSES,
    _coerce_status,
    _print_summary,
    _read_project_name,
    _render_log,
    _resolve_script,
    _stream_to_completion,
    execute,
)
from fenn.exceptions import (
    CredentialsError,
    InsufficientCreditsError,
    JobFailedError,
    RemoteError,
    WorkspaceTooLargeError,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _args(**kwargs):
    defaults = {
        "script": None,
        "max_runtime": 10,
        "tier": None,
        "detach": False,
        "include": None,
        "exclude": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ══════════════════════════════════════════════════════════════════════════════
# Module-level constants
# ══════════════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_default_script(self):
        assert DEFAULT_SCRIPT == "main.py"

    def test_terminal_statuses(self):
        assert TERMINAL_STATUSES == {"succeeded", "failed", "cancelled"}


# ══════════════════════════════════════════════════════════════════════════════
# _resolve_script
# ══════════════════════════════════════════════════════════════════════════════


class TestResolveScript:
    def test_resolves_existing_file(self, tmp_path):
        script = tmp_path / "main.py"
        script.write_text("pass")
        result = _resolve_script(str(script))
        assert result == script.resolve()

    def test_defaults_to_main_py_when_none(self, tmp_path, monkeypatch):
        script = tmp_path / "main.py"
        script.write_text("pass")
        monkeypatch.chdir(tmp_path)
        result = _resolve_script(None)
        assert result.name == "main.py"

    def test_exits_when_script_not_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("fenn.cli.run.logger"):
            with pytest.raises(SystemExit) as exc_info:
                _resolve_script("nonexistent.py")
        assert exc_info.value.code == 1

    def test_exits_with_custom_missing_script(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("fenn.cli.run.logger"):
            with pytest.raises(SystemExit) as exc_info:
                _resolve_script("custom_script.py")
        assert exc_info.value.code == 1


# ══════════════════════════════════════════════════════════════════════════════
# execute — error handling
# ══════════════════════════════════════════════════════════════════════════════


class TestExecute:
    def _run_execute(self, tmp_path, exc=None, **arg_overrides):
        script = tmp_path / "main.py"
        script.write_text("pass")
        args = _args(script=str(script), **arg_overrides)

        with patch("fenn.cli.run.logger"):
            with patch("fenn.cli.run._run_remote", side_effect=exc) as mock_run:
                return mock_run, args

    def test_calls_run_remote(self, tmp_path):
        script = tmp_path / "main.py"
        script.write_text("pass")
        args = _args(script=str(script))

        with patch("fenn.cli.run.logger"):
            with patch("fenn.cli.run._run_remote") as mock_run:
                execute(args)

        mock_run.assert_called_once()

    def test_passes_max_runtime_as_seconds(self, tmp_path):
        script = tmp_path / "main.py"
        script.write_text("pass")
        args = _args(script=str(script), max_runtime=5)
        captured = {}

        def capture(**kwargs):
            captured.update(kwargs)

        with patch("fenn.cli.run.logger"):
            with patch("fenn.cli.run._run_remote", side_effect=capture):
                execute(args)

        assert captured["max_runtime"] == 300  # 5 * 60

    def test_credentials_error_exits_2(self, tmp_path):
        script = tmp_path / "main.py"
        script.write_text("pass")
        args = _args(script=str(script))
        with patch("fenn.cli.run.logger"):
            with patch(
                "fenn.cli.run._run_remote", side_effect=CredentialsError("no key")
            ):
                with pytest.raises(SystemExit) as exc_info:
                    execute(args)
        assert exc_info.value.code == 2

    def test_workspace_too_large_exits_2(self, tmp_path):
        script = tmp_path / "main.py"
        script.write_text("pass")
        args = _args(script=str(script))
        with patch("fenn.cli.run.logger"):
            with patch(
                "fenn.cli.run._run_remote",
                side_effect=WorkspaceTooLargeError("too big"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    execute(args)
        assert exc_info.value.code == 2

    def test_insufficient_credits_exits_3(self, tmp_path):
        script = tmp_path / "main.py"
        script.write_text("pass")
        args = _args(script=str(script))
        with patch("fenn.cli.run.logger"):
            with patch(
                "fenn.cli.run._run_remote",
                side_effect=InsufficientCreditsError("broke"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    execute(args)
        assert exc_info.value.code == 3

    def test_job_failed_exits_1(self, tmp_path):
        script = tmp_path / "main.py"
        script.write_text("pass")
        args = _args(script=str(script))
        exc = JobFailedError("failed", job_id="job-123", status="failed")
        with patch("fenn.cli.run.logger"):
            with patch("fenn.cli.run._run_remote", side_effect=exc):
                with pytest.raises(SystemExit) as exc_info:
                    execute(args)
        assert exc_info.value.code == 1

    def test_remote_error_exits_1(self, tmp_path):
        script = tmp_path / "main.py"
        script.write_text("pass")
        args = _args(script=str(script))
        with patch("fenn.cli.run.logger"):
            with patch("fenn.cli.run._run_remote", side_effect=RemoteError("oops")):
                with pytest.raises(SystemExit) as exc_info:
                    execute(args)
        assert exc_info.value.code == 1

    def test_passes_tier_to_run_remote(self, tmp_path):
        script = tmp_path / "main.py"
        script.write_text("pass")
        args = _args(script=str(script), tier="gpu")
        captured = {}

        def capture(**kwargs):
            captured.update(kwargs)

        with patch("fenn.cli.run.logger"):
            with patch("fenn.cli.run._run_remote", side_effect=capture):
                execute(args)

        assert captured["tier"] == "gpu"

    def test_passes_detach_flag(self, tmp_path):
        script = tmp_path / "main.py"
        script.write_text("pass")
        args = _args(script=str(script), detach=True)
        captured = {}

        def capture(**kwargs):
            captured.update(kwargs)

        with patch("fenn.cli.run.logger"):
            with patch("fenn.cli.run._run_remote", side_effect=capture):
                execute(args)

        assert captured["detach"] is True

    def test_none_includes_becomes_empty_tuple(self, tmp_path):
        script = tmp_path / "main.py"
        script.write_text("pass")
        args = _args(script=str(script), include=None)
        captured = {}

        def capture(**kwargs):
            captured.update(kwargs)

        with patch("fenn.cli.run.logger"):
            with patch("fenn.cli.run._run_remote", side_effect=capture):
                execute(args)

        assert captured["includes"] == ()


# ══════════════════════════════════════════════════════════════════════════════
# _stream_to_completion
# ══════════════════════════════════════════════════════════════════════════════


class TestStreamToCompletion:
    def _make_client(self, events):
        client = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=iter(events))
        ctx.__exit__ = MagicMock(return_value=False)
        client.stream_events.return_value = ctx
        return client

    def test_returns_succeeded_status(self):
        events = [{"event": "status", "data": "succeeded"}]
        client = self._make_client(events)
        with patch("fenn.cli.run.logger"):
            status, billing = _stream_to_completion(client, "job-1")
        assert status == "succeeded"

    def test_returns_failed_status(self):
        events = [{"event": "status", "data": "failed"}]
        client = self._make_client(events)
        with patch("fenn.cli.run.logger"):
            status, _ = _stream_to_completion(client, "job-1")
        assert status == "failed"

    def test_returns_cancelled_status(self):
        events = [{"event": "status", "data": "cancelled"}]
        client = self._make_client(events)
        with patch("fenn.cli.run.logger"):
            status, _ = _stream_to_completion(client, "job-1")
        assert status == "cancelled"

    def test_processes_log_events(self):
        events = [
            {"event": "log", "data": {"line": "hello"}},
            {"event": "status", "data": "succeeded"},
        ]
        client = self._make_client(events)
        with patch("fenn.cli.run.logger") as mock_logger:
            _stream_to_completion(client, "job-1")
        mock_logger.info.assert_called()

    def test_collects_billing_data(self):
        billing_data = {"credits_used": 5, "credits_remaining": 95}
        events = [
            {"event": "billing", "data": billing_data},
            {"event": "status", "data": "succeeded"},
        ]
        client = self._make_client(events)
        with patch("fenn.cli.run.logger"):
            _, billing = _stream_to_completion(client, "job-1")
        assert billing == billing_data

    def test_ignores_non_dict_billing(self):
        events = [
            {"event": "billing", "data": "not a dict"},
            {"event": "status", "data": "succeeded"},
        ]
        client = self._make_client(events)
        with patch("fenn.cli.run.logger"):
            _, billing = _stream_to_completion(client, "job-1")
        assert billing == {}

    def test_unknown_event_kind_logged(self):
        events = [
            {"event": "mystery", "data": "something"},
            {"event": "status", "data": "succeeded"},
        ]
        client = self._make_client(events)
        with patch("fenn.cli.run.logger") as mock_logger:
            _stream_to_completion(client, "job-1")
        logged = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "mystery" in logged

    def test_keyboard_interrupt_cancels_job(self):
        client = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=iter([KeyboardInterrupt()]))
        ctx.__exit__ = MagicMock(return_value=False)
        client.stream_events.return_value = ctx

        def raise_on_iter(job_id):
            raise KeyboardInterrupt()

        client2 = MagicMock()
        ctx2 = MagicMock()

        class _RaisingIter:
            def __iter__(self):
                raise KeyboardInterrupt()

        ctx2.__enter__ = MagicMock(return_value=_RaisingIter())
        ctx2.__exit__ = MagicMock(return_value=False)
        client2.stream_events.return_value = ctx2

        with patch("fenn.cli.run.logger"):
            with pytest.raises(KeyboardInterrupt):
                _stream_to_completion(client2, "job-1")

        client2.cancel.assert_called_once_with("job-1")

    def test_keyboard_interrupt_cancel_failure_logged(self):
        client = MagicMock()
        ctx = MagicMock()

        class _RaisingIter:
            def __iter__(self):
                raise KeyboardInterrupt()

        ctx.__enter__ = MagicMock(return_value=_RaisingIter())
        ctx.__exit__ = MagicMock(return_value=False)
        client.stream_events.return_value = ctx
        client.cancel.side_effect = RemoteError("cancel failed")

        with patch("fenn.cli.run.logger") as mock_logger:
            with pytest.raises(KeyboardInterrupt):
                _stream_to_completion(client, "job-1")

        logged = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "Cancel" in logged or "cancel" in logged.lower()

    def test_stops_at_first_terminal_status(self):
        events = [
            {"event": "log", "data": "line 1"},
            {"event": "status", "data": "succeeded"},
            {"event": "log", "data": "should not appear"},
        ]
        client = self._make_client(events)
        with patch("fenn.cli.run.logger") as mock_logger:
            status, _ = _stream_to_completion(client, "job-1")
        assert status == "succeeded"
        # "should not appear" must not have been logged
        all_calls = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "should not appear" not in all_calls

    def test_returns_unknown_status_when_no_terminal_event(self):
        events = [{"event": "log", "data": "just a log"}]
        client = self._make_client(events)
        with patch("fenn.cli.run.logger"):
            status, _ = _stream_to_completion(client, "job-1")
        assert status == "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# _render_log
# ══════════════════════════════════════════════════════════════════════════════


class TestRenderLog:
    def test_renders_dict_with_line_key(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _render_log({"line": "hello world"})
        mock_logger.info.assert_called_once_with("hello world")

    def test_renders_dict_with_text_key(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _render_log({"text": "from text key"})
        mock_logger.info.assert_called_once_with("from text key")

    def test_renders_dict_fallback_to_str(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _render_log({"other": "value"})
        mock_logger.info.assert_called_once()

    def test_renders_plain_string(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _render_log("plain log line")
        mock_logger.info.assert_called_once_with("plain log line")

    def test_renders_non_string_data(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _render_log(42)
        mock_logger.info.assert_called_once_with("42")

    def test_line_key_preferred_over_text(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _render_log({"line": "from line", "text": "from text"})
        mock_logger.info.assert_called_once_with("from line")


# ══════════════════════════════════════════════════════════════════════════════
# _coerce_status
# ══════════════════════════════════════════════════════════════════════════════


class TestCoerceStatus:
    def test_dict_with_status_key(self):
        assert _coerce_status({"status": "succeeded"}) == "succeeded"

    def test_dict_without_status_key(self):
        assert _coerce_status({"other": "value"}) == "unknown"

    def test_plain_string(self):
        assert _coerce_status("failed") == "failed"

    def test_non_string_non_dict(self):
        assert _coerce_status(42) == "42"

    def test_empty_dict(self):
        assert _coerce_status({}) == "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# _print_summary
# ══════════════════════════════════════════════════════════════════════════════


class TestPrintSummary:
    def test_succeeded_logged(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _print_summary("succeeded", {})
        logged = mock_logger.info.call_args[0][0]
        assert "succeeded" in logged

    def test_failed_logged(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _print_summary("failed", {})
        logged = mock_logger.info.call_args[0][0]
        assert "failed" in logged

    def test_includes_wall_time(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _print_summary("succeeded", {"wall_seconds": 42.5})
        logged = mock_logger.info.call_args[0][0]
        assert "42.5" in logged

    def test_includes_credits_used(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _print_summary("succeeded", {"credits_used": 10})
        logged = mock_logger.info.call_args[0][0]
        assert "credits_used=10" in logged

    def test_includes_credits_remaining(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _print_summary("succeeded", {"credits_remaining": 90})
        logged = mock_logger.info.call_args[0][0]
        assert "credits_remaining=90" in logged

    def test_empty_billing_only_shows_status(self):
        with patch("fenn.cli.run.logger") as mock_logger:
            _print_summary("succeeded", {})
        logged = mock_logger.info.call_args[0][0]
        assert "status=succeeded" in logged
        assert "wall" not in logged
        assert "credits" not in logged

    def test_full_billing_all_parts_present(self):
        billing = {"wall_seconds": 10.0, "credits_used": 5, "credits_remaining": 95}
        with patch("fenn.cli.run.logger") as mock_logger:
            _print_summary("succeeded", billing)
        logged = mock_logger.info.call_args[0][0]
        assert "wall=10.0s" in logged
        assert "credits_used=5" in logged
        assert "credits_remaining=95" in logged


# ══════════════════════════════════════════════════════════════════════════════
# _read_project_name
# ══════════════════════════════════════════════════════════════════════════════


class TestReadProjectName:
    def test_returns_none_when_no_fenn_yaml(self, tmp_path):
        assert _read_project_name(tmp_path) is None

    def test_reads_project_name_from_yaml(self, tmp_path):
        (tmp_path / "fenn.yaml").write_text("project: my_project\n", encoding="utf-8")
        assert _read_project_name(tmp_path) == "my_project"

    def test_returns_none_when_project_key_missing(self, tmp_path):
        (tmp_path / "fenn.yaml").write_text("other: value\n", encoding="utf-8")
        assert _read_project_name(tmp_path) is None

    def test_returns_none_when_project_is_null(self, tmp_path):
        (tmp_path / "fenn.yaml").write_text("project:\n", encoding="utf-8")
        assert _read_project_name(tmp_path) is None

    def test_returns_none_on_invalid_yaml(self, tmp_path):
        (tmp_path / "fenn.yaml").write_text(":: invalid ::\n", encoding="utf-8")
        assert _read_project_name(tmp_path) is None

    def test_returns_none_on_empty_yaml(self, tmp_path):
        (tmp_path / "fenn.yaml").write_text("", encoding="utf-8")
        assert _read_project_name(tmp_path) is None

    def test_project_name_cast_to_string(self, tmp_path):
        (tmp_path / "fenn.yaml").write_text("project: 42\n", encoding="utf-8")
        result = _read_project_name(tmp_path)
        assert result == "42"
        assert isinstance(result, str)
