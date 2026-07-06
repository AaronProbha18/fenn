"""Typed exceptions for the Fenn remote service client."""

from __future__ import annotations

from typing import Optional


class RemoteError(Exception):
    """Base class for every error raised by :mod:`fenn.remote`."""


class NetworkError(RemoteError):
    """The remote host could not be reached."""


class AuthError(RemoteError):
    """The API key was missing, invalid, or revoked (HTTP 401/403)."""


class CredentialsError(RemoteError):
    """No usable API key could be resolved locally."""


class InsufficientCreditsError(RemoteError):
    """The account does not have enough credits for the request (HTTP 402)."""


class WorkspaceTooLargeError(RemoteError):
    """The packed workspace exceeds the upload size limit."""


class JobFailedError(RemoteError):
    """A remote job finished in a non-success terminal state."""

    def __init__(
        self,
        message: str,
        *,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.job_id = job_id
        self.status = status
