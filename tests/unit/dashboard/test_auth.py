from unittest.mock import MagicMock, patch

import pytest
import requests

from fenn.dashboard.auth import (
    current_user,
    exchange_code,
    login_required,
    validate_token,
)
from fenn.exceptions import AuthUnreachableError, InvalidTokenError

# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

VALID_TOKEN = "fdt_" + "a" * 43  # exactly matches _TOKEN_RE


def _mock_response(
    status_code=200,
    json_body=None,
    content_type="application/json",
    content_size=100,
):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"Content-Type": content_type}
    resp.content = b"x" * content_size
    resp.json.return_value = json_body or {}
    return resp


# ══════════════════════════════════════════════════════════════════════════════
# current_user / login_required — tested via Flask app context
# ══════════════════════════════════════════════════════════════════════════════


class TestCurrentUser:
    def _make_app(self):
        from flask import Flask

        app = Flask(__name__)
        app.secret_key = "test"
        return app

    def test_returns_none_when_no_session(self):
        app = self._make_app()
        with app.test_request_context("/"):
            result = current_user()
        assert result is None

    def test_returns_user_from_session(self):
        app = self._make_app()
        with app.test_request_context("/"):
            from flask import session

            session["user"] = {"user_id": "u1", "email": "a@b.com"}
            result = current_user()
        assert result == {"user_id": "u1", "email": "a@b.com"}

    def test_caches_on_g(self):
        app = self._make_app()
        with app.test_request_context("/"):
            from flask import session

            session["user"] = {"user_id": "u1", "email": "a@b.com"}
            first = current_user()
            session["user"] = {"user_id": "changed"}
            second = current_user()
        assert first == second  # served from g cache


class TestLoginRequired:
    def _make_app(self):
        from flask import Flask

        app = Flask(__name__)
        app.secret_key = "test"
        return app

    def test_redirects_when_not_logged_in(self):
        app = self._make_app()

        @app.route("/protected")
        @login_required
        def protected():
            return "ok"

        @app.route("/connect")
        def connect():
            return "connect"

        with app.test_client() as client:
            resp = client.get("/protected")
        assert resp.status_code == 302

    def test_passes_through_when_logged_in(self):
        from fenn.dashboard.auth import login_required

        app = self._make_app()

        @app.route("/protected")
        @login_required
        def protected():
            return "ok", 200

        @app.route("/connect")
        def connect():
            return "connect"

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user"] = {"user_id": "u1", "email": "a@b.com"}
            resp = client.get("/protected")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# validate_token
# ══════════════════════════════════════════════════════════════════════════════


class TestValidateToken:
    def test_empty_token_raises(self):
        from fenn.dashboard.auth import validate_token

        with pytest.raises(InvalidTokenError, match="empty token"):
            validate_token("")

    def test_malformed_token_wrong_prefix(self):
        with pytest.raises(InvalidTokenError, match="malformed token"):
            validate_token("bad_" + "a" * 43)

    def test_malformed_token_too_short(self):
        with pytest.raises(InvalidTokenError, match="malformed token"):
            validate_token("fdt_short")

    def test_malformed_token_too_long(self):
        with pytest.raises(InvalidTokenError, match="malformed token"):
            validate_token("fdt_" + "a" * 100)

    def test_token_with_whitespace_stripped(self):
        resp = _mock_response(json_body={"user_id": "u1", "email": "a@b.com"})
        with patch("fenn.dashboard.auth.requests.get", return_value=resp):
            result = validate_token("  " + VALID_TOKEN + "  ")
        assert result["user_id"] == "u1"

    def test_success_returns_user_dict(self):
        resp = _mock_response(json_body={"user_id": "u1", "email": "a@b.com"})
        with patch("fenn.dashboard.auth.requests.get", return_value=resp):
            result = validate_token(VALID_TOKEN)
        assert result == {"user_id": "u1", "email": "a@b.com"}

    def test_401_raises_invalid_token(self):
        resp = _mock_response(status_code=401)
        with patch("fenn.dashboard.auth.requests.get", return_value=resp):
            with pytest.raises(InvalidTokenError, match="token rejected"):
                validate_token(VALID_TOKEN)

    def test_non_200_non_401_raises_unreachable(self):
        resp = _mock_response(status_code=500)
        with patch("fenn.dashboard.auth.requests.get", return_value=resp):
            with patch("fenn.dashboard.auth.logger"):
                with pytest.raises(AuthUnreachableError, match="unexpected status 500"):
                    validate_token(VALID_TOKEN)

    def test_network_error_raises_unreachable(self):
        with patch(
            "fenn.dashboard.auth.requests.get",
            side_effect=requests.ConnectionError("no route"),
        ):
            with patch("fenn.dashboard.auth.logger"):
                with pytest.raises(AuthUnreachableError):
                    validate_token(VALID_TOKEN)

    def test_non_json_content_type_raises(self):
        resp = _mock_response(content_type="text/html")
        with patch("fenn.dashboard.auth.requests.get", return_value=resp):
            with pytest.raises(AuthUnreachableError, match="content-type"):
                validate_token(VALID_TOKEN)

    def test_response_too_large_raises(self):
        resp = _mock_response(content_size=5000)
        with patch("fenn.dashboard.auth.requests.get", return_value=resp):
            with pytest.raises(AuthUnreachableError, match="too large"):
                validate_token(VALID_TOKEN)

    def test_malformed_json_raises(self):
        resp = _mock_response()
        resp.json.side_effect = ValueError("bad json")
        with patch("fenn.dashboard.auth.requests.get", return_value=resp):
            with pytest.raises(AuthUnreachableError, match="malformed JSON"):
                validate_token(VALID_TOKEN)

    def test_missing_user_id_raises(self):
        resp = _mock_response(json_body={"email": "a@b.com"})
        with patch("fenn.dashboard.auth.requests.get", return_value=resp):
            with pytest.raises(AuthUnreachableError, match="missing user_id"):
                validate_token(VALID_TOKEN)

    def test_missing_email_raises(self):
        resp = _mock_response(json_body={"user_id": "u1"})
        with patch("fenn.dashboard.auth.requests.get", return_value=resp):
            with pytest.raises(AuthUnreachableError, match="missing user_id"):
                validate_token(VALID_TOKEN)

    def test_non_string_user_id_raises(self):
        resp = _mock_response(json_body={"user_id": 123, "email": "a@b.com"})
        with patch("fenn.dashboard.auth.requests.get", return_value=resp):
            with pytest.raises(AuthUnreachableError):
                validate_token(VALID_TOKEN)

    def test_sends_bearer_header(self):
        resp = _mock_response(json_body={"user_id": "u1", "email": "a@b.com"})
        with patch("fenn.dashboard.auth.requests.get", return_value=resp) as mock_get:
            validate_token(VALID_TOKEN)
        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["Authorization"] == f"Bearer {VALID_TOKEN}"


# ══════════════════════════════════════════════════════════════════════════════
# exchange_code
# ══════════════════════════════════════════════════════════════════════════════


class TestExchangeCode:
    def test_empty_code_raises(self):
        with pytest.raises(InvalidTokenError, match="empty code"):
            exchange_code("")

    def test_success_returns_full_dict(self):
        resp = _mock_response(
            json_body={"user_id": "u1", "email": "a@b.com", "token": VALID_TOKEN}
        )
        with patch("fenn.dashboard.auth.requests.post", return_value=resp):
            result = exchange_code("one-time-code")
        assert result == {"user_id": "u1", "email": "a@b.com", "token": VALID_TOKEN}

    def test_400_raises_invalid_token(self):
        resp = _mock_response(status_code=400)
        with patch("fenn.dashboard.auth.requests.post", return_value=resp):
            with pytest.raises(InvalidTokenError, match="code rejected"):
                exchange_code("bad-code")

    def test_non_200_non_400_raises_unreachable(self):
        resp = _mock_response(status_code=503)
        with patch("fenn.dashboard.auth.requests.post", return_value=resp):
            with patch("fenn.dashboard.auth.logger"):
                with pytest.raises(AuthUnreachableError, match="unexpected status 503"):
                    exchange_code("some-code")

    def test_network_error_raises_unreachable(self):
        with patch(
            "fenn.dashboard.auth.requests.post",
            side_effect=requests.Timeout("timed out"),
        ):
            with patch("fenn.dashboard.auth.logger"):
                with pytest.raises(AuthUnreachableError):
                    exchange_code("some-code")

    def test_non_json_content_type_raises(self):
        resp = _mock_response(content_type="text/plain")
        with patch("fenn.dashboard.auth.requests.post", return_value=resp):
            with pytest.raises(AuthUnreachableError, match="content-type"):
                exchange_code("some-code")

    def test_response_too_large_raises(self):
        resp = _mock_response(content_size=5000)
        with patch("fenn.dashboard.auth.requests.post", return_value=resp):
            with pytest.raises(AuthUnreachableError, match="too large"):
                exchange_code("some-code")

    def test_malformed_json_raises(self):
        resp = _mock_response()
        resp.json.side_effect = ValueError("bad json")
        with patch("fenn.dashboard.auth.requests.post", return_value=resp):
            with pytest.raises(AuthUnreachableError, match="malformed JSON"):
                exchange_code("some-code")

    def test_missing_token_in_response_raises(self):
        resp = _mock_response(json_body={"user_id": "u1", "email": "a@b.com"})
        with patch("fenn.dashboard.auth.requests.post", return_value=resp):
            with pytest.raises(AuthUnreachableError, match="missing"):
                exchange_code("some-code")

    def test_empty_token_in_response_raises(self):
        resp = _mock_response(
            json_body={"user_id": "u1", "email": "a@b.com", "token": ""}
        )
        with patch("fenn.dashboard.auth.requests.post", return_value=resp):
            with pytest.raises(AuthUnreachableError, match="missing"):
                exchange_code("some-code")

    def test_missing_user_id_raises(self):
        resp = _mock_response(json_body={"email": "a@b.com", "token": VALID_TOKEN})
        with patch("fenn.dashboard.auth.requests.post", return_value=resp):
            with pytest.raises(AuthUnreachableError, match="missing"):
                exchange_code("some-code")

    def test_posts_code_as_json(self):
        resp = _mock_response(
            json_body={"user_id": "u1", "email": "a@b.com", "token": VALID_TOKEN}
        )
        with patch("fenn.dashboard.auth.requests.post", return_value=resp) as mock_post:
            exchange_code("my-code")
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {"code": "my-code"}
