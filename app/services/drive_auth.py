"""Non-interactive Drive OAuth for workers. Consent belongs to the owner.

Both the legacy daily runner and the studio use this implementation. A cron
must never open a browser or replace a failed login with an empty inventory.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class DriveAuthorizationRequired(RuntimeError):
    """The owner must renew read-only Drive access on their own device."""


REAUTHORIZATION_MESSAGE = (
    "Google Drive needs owner reauthorization. Run scripts/drive-oauth-setup.py "
    "on your laptop, then securely replace the VPS token.json. "
    "Do not paste credentials into Telegram. No browser was opened on the server."
)


def require_token_file(token_path: Path) -> None:
    """Workers need the saved grant, not the desktop consent client file."""
    if not token_path.is_file():
        raise DriveAuthorizationRequired(REAUTHORIZATION_MESSAGE)


def save_token(token_path: Path, token_json: str) -> None:
    """Atomic, owner-only replacement; never truncate the last usable token."""
    fd, temporary = tempfile.mkstemp(prefix=".drive-token-", dir=token_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token_json)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, token_path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_credentials(token_path: Path, scopes: list[str]):
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    require_token_file(token_path)
    try:
        credentials = Credentials.from_authorized_user_file(token_path, scopes)
    except (ValueError, KeyError):
        raise DriveAuthorizationRequired(REAUTHORIZATION_MESSAGE) from None
    if credentials.valid:
        return credentials
    if not credentials.refresh_token:
        raise DriveAuthorizationRequired(REAUTHORIZATION_MESSAGE)
    try:
        credentials.refresh(Request())
    except RefreshError:
        raise DriveAuthorizationRequired(REAUTHORIZATION_MESSAGE) from None
    if not credentials.valid:
        raise DriveAuthorizationRequired(REAUTHORIZATION_MESSAGE)
    save_token(token_path, credentials.to_json())
    return credentials
