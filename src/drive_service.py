from dataclasses import dataclass
from io import FileIO
from pathlib import Path

from .settings import GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_DRIVE_ENABLED, GOOGLE_DRIVE_ROOT_FOLDER_ID


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
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            return AssetInventory(enabled=False, summary="Google Drive dependencies are not installed.", files=[])

        credentials_path = Path(GOOGLE_APPLICATION_CREDENTIALS)
        if not credentials_path.exists():
            return AssetInventory(enabled=False, summary="credentials.json was not found.", files=[])

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
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_file(
            Path(GOOGLE_APPLICATION_CREDENTIALS),
            scopes=scopes,
        )
        return build("drive", "v3", credentials=credentials)

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
