"""Tests for the `fenn run` CLI wiring."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from fenn.cli import build_parser
from fenn.remote.client import DEFAULT_REMOTE_HOST
from fenn.remote.credentials import Credentials


def test_run_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["run"])
    assert args.command == "run"
    assert args.script is None
    assert not hasattr(args, "host")
    assert args.api_key is None
    assert args.profile is None
    assert args.detach is False
    assert args.no_download is False
    assert args.max_runtime == 3600


def test_run_parser_collects_includes_and_excludes():
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "main.py",
            "--include",
            "data",
            "--include",
            "models",
            "--exclude",
            "*.tmp",
        ]
    )
    assert args.script == "main.py"
    assert args.include == ["data", "models"]
    assert args.exclude == ["*.tmp"]


def test_run_parser_rejects_host():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "main.py", "--host", "http://localhost:8000"])


def test_run_execute_invokes_remote(tmp_path):
    script = tmp_path / "main.py"
    script.write_text("RAN = True\n", encoding="utf-8")

    from fenn.cli import run as run_module

    parser = build_parser()
    args = parser.parse_args(["run", str(script), "--api-key", "fk_test"])

    with patch("fenn.cli.run._run_remote") as run_remote:
        run_module.execute(args)
        run_remote.assert_called_once()
        assert run_remote.call_args.kwargs["script_path"] == script.resolve()
        assert run_remote.call_args.kwargs["explicit_key"] == "fk_test"
        assert "host" not in run_remote.call_args.kwargs


def test_run_remote_uses_fixed_remote_host(tmp_path):
    from fenn.cli import run as run_module

    class Pack:
        def __init__(self):
            self.file_count = 1
            self.uncompressed_bytes = 128
            self.path = tmp_path / "workspace.tar.gz"
            self.script_relpath = "main.py"
            self.cleaned = False

        def cleanup(self):
            self.cleaned = True

    pack = Pack()

    with (
        patch(
            "fenn.remote.credentials.resolve_api_key",
            return_value=Credentials(profile="default", api_key="fk_test"),
        ),
        patch("fenn.remote.workspace.pack_workspace", return_value=pack),
        patch("fenn.remote.workspace.detect_venv_spec", return_value=None),
        patch("fenn.remote.client.RemoteClient") as remote_client,
    ):
        remote_client.return_value.__enter__.return_value.submit_job.return_value = {
            "job_id": "job_1",
            "credit_hold": 1,
        }

        run_module._run_remote(
            script_path=tmp_path / "main.py",
            explicit_key="fk_test",
            profile=None,
            max_runtime=3600,
            detach=True,
            download=False,
            includes=(),
            excludes=(),
        )

    remote_client.assert_called_once_with(DEFAULT_REMOTE_HOST, "fk_test")
    assert pack.cleaned is True


def test_run_local_supports_relative_imports(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    script = project / "main.py"
    script.write_text(
        "from pathlib import Path\n"
        "from .modules import VALUE\n"
        "Path('result.txt').write_text(VALUE, encoding='utf-8')\n",
        encoding="utf-8",
    )
    (project / "modules.py").write_text("VALUE = 'ok'\n", encoding="utf-8")

    from fenn.remote.local_runner import run_local

    run_local(script)

    assert (project / "result.txt").read_text(encoding="utf-8") == "ok"


def test_run_missing_script_exits(tmp_path, capsys):
    from fenn.cli import run as run_module

    parser = build_parser()
    args = parser.parse_args(["run", str(tmp_path / "nope.py")])

    with pytest.raises(SystemExit) as exc:
        run_module.execute(args)
    assert exc.value.code == 1


def test_auth_parser_subcommands():
    parser = build_parser()
    args = parser.parse_args(["auth", "login", "--profile", "work"])
    assert args.command == "auth"
    assert args.auth_command == "login"
    assert args.profile == "work"
    assert not hasattr(args, "host")


def test_auth_login_parser_rejects_host():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["auth", "login", "--host", "http://localhost:8000"])


def test_dashboard_parser_rejects_host():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["dashboard", "--host", "0.0.0.0"])


def test_auth_status_uses_fixed_remote_host():
    from fenn.cli import auth as auth_module

    parser = build_parser()
    args = parser.parse_args(["auth", "status"])

    with (
        patch(
            "fenn.cli.auth.load_credentials",
            return_value=Credentials(profile="default", api_key="fk_test"),
        ),
        patch("fenn.remote.client.RemoteClient") as remote_client,
    ):
        remote_client.return_value.__enter__.return_value.me.return_value = {
            "credits": 10,
            "plan": "test",
        }

        auth_module.execute(args)

    remote_client.assert_called_once_with(DEFAULT_REMOTE_HOST, "fk_test")
