from pathlib import Path
from unittest.mock import Mock

import pytest

from app.services.drive_auth import DriveAuthorizationRequired, load_credentials, save_token

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


@pytest.fixture
def token(tmp_path, monkeypatch):
    path = tmp_path / "token.json"
    path.write_text("synthetic-old-token")
    credentials = Mock(valid=False, refresh_token="synthetic-refresh-token")
    monkeypatch.setattr(
        "google.oauth2.credentials.Credentials.from_authorized_user_file",
        Mock(return_value=credentials),
    )
    browser = Mock(side_effect=AssertionError("Workers must never initiate interactive consent"))
    monkeypatch.setattr("google_auth_oauthlib.flow.InstalledAppFlow.run_local_server", browser)
    return path, credentials, browser


def test_valid_token_never_refreshes_or_opens_browser(token):
    path, credentials, browser = token
    credentials.valid = True
    assert load_credentials(path, SCOPES) is credentials
    credentials.refresh.assert_not_called()
    browser.assert_not_called()
    assert path.read_text() == "synthetic-old-token"


def test_refresh_is_persisted_atomically_and_private(token):
    path, credentials, browser = token
    credentials.to_json.return_value = '{"token":"synthetic-new-token"}'
    credentials.refresh.side_effect = lambda request: setattr(credentials, "valid", True)
    assert load_credentials(path, SCOPES) is credentials
    assert path.read_text() == credentials.to_json.return_value
    assert path.stat().st_mode & 0o777 == 0o600
    assert list(path.parent.iterdir()) == [path]
    browser.assert_not_called()


def test_rejected_refresh_preserves_token_and_asks_owner(token):
    from google.auth.exceptions import RefreshError

    path, credentials, browser = token
    credentials.refresh.side_effect = RefreshError("synthetic-sensitive-provider-response")
    with pytest.raises(DriveAuthorizationRequired) as exc:
        load_credentials(path, SCOPES)
    assert "reauthorization" in str(exc.value)
    assert "sensitive" not in str(exc.value)
    assert path.read_text() == "synthetic-old-token"
    browser.assert_not_called()


@pytest.mark.parametrize("failure", ["missing", "no-refresh", "invalid-json", "still-invalid"])
def test_unusable_credentials_fail_closed(token, monkeypatch, failure):
    path, credentials, browser = token
    if failure == "missing":
        path.unlink()
    elif failure == "no-refresh":
        credentials.refresh_token = None
    elif failure == "invalid-json":
        monkeypatch.setattr(
            "google.oauth2.credentials.Credentials.from_authorized_user_file",
            Mock(side_effect=ValueError("malformed synthetic token")),
        )
    with pytest.raises(DriveAuthorizationRequired):
        load_credentials(path, SCOPES)
    browser.assert_not_called()


def test_atomic_write_failure_preserves_previous_token(token, monkeypatch):
    path, _, _ = token
    monkeypatch.setattr("app.services.drive_auth.os.replace", Mock(side_effect=OSError("disk error")))
    with pytest.raises(OSError):
        save_token(path, "new-synthetic-token")
    assert path.read_text() == "synthetic-old-token"
    assert list(path.parent.iterdir()) == [path]


def test_studio_and_legacy_share_headless_auth(app_env, monkeypatch):
    import src.drive_service as legacy
    from app.services.drive import GoogleDriveService

    loader = Mock(return_value="synthetic-credentials")
    monkeypatch.setattr("app.services.drive_auth.load_credentials", loader)
    monkeypatch.setattr(legacy, "GOOGLE_OAUTH_TOKEN_FILE", "nested-token.json")
    assert legacy.GoogleDriveService()._oauth_credentials() == "synthetic-credentials"
    assert loader.call_args.args[0] == legacy.ROOT_DIR / "nested-token.json"
    assert GoogleDriveService()._oauth_credentials() == "synthetic-credentials"
    assert isinstance(loader.call_args.args[0], Path)
