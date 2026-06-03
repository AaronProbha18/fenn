"""Client-side remote execution helpers for the Fenn premium service.

This package is imported when ``fenn run`` or ``fenn auth`` is invoked.
"""

from fenn.remote.client import DEFAULT_REMOTE_HOST, RemoteClient
from fenn.remote.credentials import (
    DEFAULT_PROFILE,
    Credentials,
    load_credentials,
    resolve_api_key,
    write_credentials,
)
from fenn.remote.exceptions import (
    CredentialsError,
    InsufficientCreditsError,
    JobFailedError,
    RemoteError,
    WorkspaceTooLargeError,
)
from fenn.remote.workspace import pack_workspace

__all__ = [
    "RemoteClient",
    "DEFAULT_REMOTE_HOST",
    "Credentials",
    "CredentialsError",
    "DEFAULT_PROFILE",
    "load_credentials",
    "resolve_api_key",
    "write_credentials",
    "RemoteError",
    "InsufficientCreditsError",
    "JobFailedError",
    "WorkspaceTooLargeError",
    "pack_workspace",
]
