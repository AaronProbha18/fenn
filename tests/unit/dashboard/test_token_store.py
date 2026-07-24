import json
import os
import stat
from pathlib import Path
from unittest.mock import patch

import fenn.dashboard.token_store as token_store

# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

VALID_TOKEN = "fdt_" + "a" * 43
VALID_USER = {"user_id": "u1", "email": "a@b.com"}
VALID_PAYLOAD = {"token": VALID_TOKEN, "user": VALID_USER}


def _write_path(tmp_path, payload):
    p = tmp_path / "dashboard_session.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


# ══════════════════════════════════════════════════════════════════════════════
# path()
# ══════════════════════════════════════════════════════════════════════════════


class TestPath:
    def test_returns_path_object(self):
        assert isinstance(token_store.path(), Path)

    def test_ends_with_expected_filename(self):
        assert token_store.path().name == "dashboard_session.json"

    def test_is_under_home_fenn(self):
        p = token_store.path()
        assert p.parent.name == ".fenn"


# ══════════════════════════════════════════════════════════════════════════════
# _is_valid
# ══════════════════════════════════════════════════════════════════════════════


class TestIsValid:
    def test_valid_payload(self):
        assert token_store._is_valid(VALID_PAYLOAD) is True

    def test_non_dict_invalid(self):
        assert token_store._is_valid("string") is False
        assert token_store._is_valid(None) is False
        assert token_store._is_valid([]) is False

    def test_missing_token_invalid(self):
        assert token_store._is_valid({"user": VALID_USER}) is False

    def test_empty_token_invalid(self):
        assert token_store._is_valid({"token": "", "user": VALID_USER}) is False

    def test_non_string_token_invalid(self):
        assert token_store._is_valid({"token": 123, "user": VALID_USER}) is False

    def test_missing_user_invalid(self):
        assert token_store._is_valid({"token": VALID_TOKEN}) is False

    def test_non_dict_user_invalid(self):
        assert token_store._is_valid({"token": VALID_TOKEN, "user": "string"}) is False

    def test_missing_user_id_invalid(self):
        payload = {"token": VALID_TOKEN, "user": {"email": "a@b.com"}}
        assert token_store._is_valid(payload) is False

    def test_missing_email_invalid(self):
        payload = {"token": VALID_TOKEN, "user": {"user_id": "u1"}}
        assert token_store._is_valid(payload) is False

    def test_non_string_user_id_invalid(self):
        payload = {"token": VALID_TOKEN, "user": {"user_id": 1, "email": "a@b.com"}}
        assert token_store._is_valid(payload) is False

    def test_non_string_email_invalid(self):
        payload = {"token": VALID_TOKEN, "user": {"user_id": "u1", "email": None}}
        assert token_store._is_valid(payload) is False


# ══════════════════════════════════════════════════════════════════════════════
# load()
# ══════════════════════════════════════════════════════════════════════════════


class TestLoad:
    def test_returns_none_when_file_missing(self, tmp_path):
        p = tmp_path / "missing.json"
        with patch.object(token_store, "_PATH", p):
            assert token_store.load() is None

    def test_returns_session_for_valid_file(self, tmp_path):
        p = _write_path(tmp_path, VALID_PAYLOAD)
        with patch.object(token_store, "_PATH", p):
            result = token_store.load()
        assert result is not None
        assert result["token"] == VALID_TOKEN
        assert result["user"]["user_id"] == "u1"
        assert result["user"]["email"] == "a@b.com"

    def test_returns_none_and_clears_on_invalid_json(self, tmp_path):
        p = tmp_path / "dashboard_session.json"
        p.write_text("not json {{", encoding="utf-8")
        with patch.object(token_store, "_PATH", p):
            result = token_store.load()
        assert result is None
        assert not p.exists()

    def test_returns_none_and_clears_on_invalid_payload(self, tmp_path):
        p = _write_path(tmp_path, {"wrong": "data"})
        with patch.object(token_store, "_PATH", p):
            result = token_store.load()
        assert result is None
        assert not p.exists()

    def test_returns_none_and_clears_on_unicode_error(self, tmp_path):
        p = tmp_path / "dashboard_session.json"
        p.write_bytes(b"\xff\xfe invalid utf-8 \x80")
        with patch.object(token_store, "_PATH", p):
            with patch.object(token_store, "clear") as mock_clear:
                result = token_store.load()
        assert result is None
        mock_clear.assert_called_once()

    def test_returns_none_on_os_error(self, tmp_path):
        p = tmp_path / "dashboard_session.json"
        with patch.object(token_store, "_PATH", p):
            with patch("pathlib.Path.read_text", side_effect=OSError("perm")):
                result = token_store.load()
        assert result is None

    def test_only_returns_expected_keys(self, tmp_path):
        payload = {**VALID_PAYLOAD, "extra_field": "should be ignored"}
        p = _write_path(tmp_path, payload)
        with patch.object(token_store, "_PATH", p):
            result = token_store.load()
        assert "extra_field" not in result
        assert set(result.keys()) == {"token", "user"}


# ══════════════════════════════════════════════════════════════════════════════
# save()
# ══════════════════════════════════════════════════════════════════════════════


class TestSave:
    def test_writes_valid_json(self, tmp_path):
        p = tmp_path / ".fenn" / "dashboard_session.json"
        with patch.object(token_store, "_PATH", p):
            token_store.save(VALID_TOKEN, VALID_USER)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["token"] == VALID_TOKEN
        assert data["user"]["user_id"] == "u1"
        assert data["user"]["email"] == "a@b.com"

    def test_creates_parent_directory(self, tmp_path):
        p = tmp_path / "nested" / "dir" / "dashboard_session.json"
        with patch.object(token_store, "_PATH", p):
            token_store.save(VALID_TOKEN, VALID_USER)
        assert p.exists()

    def test_sets_posix_permissions(self, tmp_path):
        p = tmp_path / ".fenn" / "dashboard_session.json"
        with patch.object(token_store, "_PATH", p):
            token_store.save(VALID_TOKEN, VALID_USER)
        if os.name != "nt":
            mode = stat.S_IMODE(p.stat().st_mode)
            assert mode == 0o600

    def test_logs_warning_on_os_error(self, tmp_path):
        p = tmp_path / ".fenn" / "dashboard_session.json"
        with patch.object(token_store, "_PATH", p):
            with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
                with patch.object(token_store, "logger") as mock_logger:
                    token_store.save(VALID_TOKEN, VALID_USER)
        mock_logger.warning.assert_called_once()

    def test_chmod_failure_does_not_raise(self, tmp_path):
        p = tmp_path / ".fenn" / "dashboard_session.json"
        with patch.object(token_store, "_PATH", p):
            with patch("os.chmod", side_effect=OSError("no chmod")):
                token_store.save(VALID_TOKEN, VALID_USER)  # should not raise
        assert p.exists()

    def test_only_saves_user_id_and_email(self, tmp_path):
        p = tmp_path / ".fenn" / "dashboard_session.json"
        user_with_extra = {**VALID_USER, "extra": "should not be saved"}
        with patch.object(token_store, "_PATH", p):
            token_store.save(VALID_TOKEN, user_with_extra)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "extra" not in data["user"]


# ══════════════════════════════════════════════════════════════════════════════
# clear()
# ══════════════════════════════════════════════════════════════════════════════


class TestClear:
    def test_removes_existing_file(self, tmp_path):
        p = _write_path(tmp_path, VALID_PAYLOAD)
        with patch.object(token_store, "_PATH", p):
            token_store.clear()
        assert not p.exists()

    def test_no_op_when_file_missing(self, tmp_path):
        p = tmp_path / "dashboard_session.json"
        with patch.object(token_store, "_PATH", p):
            token_store.clear()  # should not raise

    def test_logs_warning_on_os_error(self, tmp_path):
        p = _write_path(tmp_path, VALID_PAYLOAD)
        with patch.object(token_store, "_PATH", p):
            with patch("pathlib.Path.unlink", side_effect=OSError("perm denied")):
                with patch.object(token_store, "logger") as mock_logger:
                    token_store.clear()
        mock_logger.warning.assert_called_once()

    def test_load_returns_none_after_clear(self, tmp_path):
        p = _write_path(tmp_path, VALID_PAYLOAD)
        with patch.object(token_store, "_PATH", p):
            token_store.clear()
            result = token_store.load()
        assert result is None
