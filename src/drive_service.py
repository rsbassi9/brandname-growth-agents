from dataclasses import dataclass
from pathlib import Path

from .settings import GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_DRIVE_ENABLED, GOOGLE_DRIVE_ROOT_FOLDER_ID


@dataclass
class AssetInventory:
    enabled: bool
    summary: str


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
            )

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            return AssetInventory(enabled=False, summary="Google Drive dependencies are not installed.")

        credentials_path = Path(GOOGLE_APPLICATION_CREDENTIALS)
        if not credentials_path.exists():
            return AssetInventory(enabled=False, summary="credentials.json was not found.")

        scopes = ["https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_file(credentials_path, scopes=scopes)
        service = build("drive", "v3", credentials=credentials)

        query = f"'{GOOGLE_DRIVE_ROOT_FOLDER_ID}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name, mimeType, modifiedTime)").execute()
        files = results.get("files", [])

        if not files:
            return AssetInventory(enabled=True, summary="Google Drive folder is connected, but no assets were found.")

        lines = ["Google Drive asset inventory:"]
        for item in files[:80]:
            lines.append(f"- {item['name']} ({item['mimeType']}, modified {item.get('modifiedTime', 'unknown')})")

        return AssetInventory(enabled=True, summary="\n".join(lines))
