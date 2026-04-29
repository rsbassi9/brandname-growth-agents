from dataclasses import dataclass
from io import FileIO
from pathlib import Path

from .settings import (
    GOOGLE_APPLICATION_CREDENTIALS,
    GOOGLE_AUTH_MODE,
    GOOGLE_DRIVE_ENABLED,
    GOOGLE_DRIVE_ROOT_FOLDER_ID,
    GOOGLE_OAUTH_CLIENT_FILE,
    GOOGLE_OAUTH_TOKEN_FILE,
)


DRIVE_READONLY_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


@dataclass
class AssetInventory:
    enabled: bool
    summary: str
    files: list[dict]


class GoogleDriveService:
    def __init__(self) -> None:
        self.enabled = GOOGLE_DRIVE_ENABLED and bool(GOOGLE_DRIVE_ROOT_FOLDER_ID)

    def get_asset_inventory(self) -> AssetInventory:
        if not self.enabled:
            return AssetInventory(
                enabled=False,
                summary=(
                    "Google Drive is not enabled. Use the local brand brief and request assets by category: "
                    "painting process, digital reconstruction, product photos, and short video clips."
                ),
                files=[],
            )

        try:
            self._assert_drive_dependencies()
        except ImportError:
            return AssetInventory(enabled=False, summary="Google Drive dependencies are not installed.", files=[])

        missing_auth = self._missing_auth_message()
        if missing_auth:
            return AssetInventory(enabled=False, summary=missing_auth, files=[])

        service = self._build_service()
        files = self._list_files(service, GOOGLE_DRIVE_ROOT_FOLDER_ID)

        if not files:
            return AssetInventory(enabled=True, summary="Google Drive folder is connected, but no assets were found.", files=[])

        lines = ["Google Drive asset inventory:"]
        for item in files[:80]:
            lines.append(f"- {item['name']} ({item['mimeType']}, modified {item.get('modifiedTime', 'unknown')})")

        return AssetInventory(enabled=True, summary="\n".join(lines), files=files)

    def download_image_assets(self, destination: Path, limit: int) -> list[Path]:
        if not self.enabled:
            return []

        service = self._build_service()
        files = [
            item
            for item in self._list_files(service, GOOGLE_DRIVE_ROOT_FOLDER_ID)
            if item.get("mimeType", "").startswith("image/")
        ][:limit]

        destination.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []

        for item in files:
            suffix = self._suffix_for_mime(item.get("mimeType", ""))
            safe_name = "".join(char if char.isalnum() or char in ("-", "_") else "-" for char in item["name"])
            path = destination / f"{item['id']}-{safe_name}{suffix}"
            request = service.files().get_media(fileId=item["id"])
            with FileIO(path, "wb") as handle:
                downloader = self._media_downloader(handle, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            downloaded.append(path)

        return downloaded

    def _build_service(self):
        from googleapiclient.discovery import build

        if GOOGLE_AUTH_MODE == "service_account":
            credentials = self._service_account_credentials()
        else:
            credentials = self._oauth_credentials()

        return build("drive", "v3", credentials=credentials)

    def _assert_drive_dependencies(self) -> None:
        import google.oauth2.credentials  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        import googleapiclient.discovery  # noqa: F401

    def _missing_auth_message(self) -> str:
        if GOOGLE_AUTH_MODE == "service_account":
            credentials_path = Path(GOOGLE_APPLICATION_CREDENTIALS)
            if not credentials_path.exists():
                return f"{GOOGLE_APPLICATION_CREDENTIALS} was not found."
            return ""

        client_path = Path(GOOGLE_OAUTH_CLIENT_FILE)
        if not client_path.exists():
            return f"{GOOGLE_OAUTH_CLIENT_FILE} was not found. Download an OAuth Desktop client JSON from Google Cloud."
        return ""

    def _service_account_credentials(self):
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(
            Path(GOOGLE_APPLICATION_CREDENTIALS),
            scopes=DRIVE_READONLY_SCOPES,
        )

    def _oauth_credentials(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        token_path = Path(GOOGLE_OAUTH_TOKEN_FILE)
        credentials = None

        if token_path.exists():
            credentials = Credentials.from_authorized_user_file(token_path, DRIVE_READONLY_SCOPES)

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_OAUTH_CLIENT_FILE, DRIVE_READONLY_SCOPES)
            credentials = flow.run_local_server(port=0)
            token_path.write_text(credentials.to_json(), encoding="utf-8")

        return credentials

    def _list_files(self, service, folder_id: str) -> list[dict]:
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name, mimeType, modifiedTime)").execute()
        files = results.get("files", [])
        expanded: list[dict] = []

        for item in files:
            if item.get("mimeType") == "application/vnd.google-apps.folder":
                expanded.extend(self._list_files(service, item["id"]))
            else:
                expanded.append(item)

        return expanded

    def _media_downloader(self, handle, request):
        from googleapiclient.http import MediaIoBaseDownload

        return MediaIoBaseDownload(handle, request)

    def _suffix_for_mime(self, mime_type: str) -> str:
        return {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }.get(mime_type, ".img")
