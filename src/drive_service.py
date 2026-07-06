from dataclasses import dataclass
import csv
from io import FileIO
from pathlib import Path
from collections import Counter
from urllib.parse import parse_qs, urlparse

from .settings import (
    GOOGLE_APPLICATION_CREDENTIALS,
    GOOGLE_AUTH_MODE,
    GOOGLE_DRIVE_ENABLED,
    GOOGLE_DRIVE_ROOT_FOLDER_ID,
    GOOGLE_OAUTH_CLIENT_FILE,
    GOOGLE_OAUTH_TOKEN_FILE,
    ROOT_DIR,
)
from .asset_design_roles import enrich_asset_design_roles


DRIVE_READONLY_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
CREATIVE_BUCKET_ORDER = [
    "First Post Inspiration",
    "Store Products",
    "Shoot Photos",
    "Photoshoot / Campaign",
    "Process / Studio",
    "Design Assets",
    "Video",
    "Other",
]


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
        files = self._list_files(service, self._folder_id())
        manual_tags = self._manual_asset_tags()

        if not files:
            return AssetInventory(enabled=True, summary="Google Drive folder is connected, but no assets were found.", files=[])

        for item in files:
            manual_tag = manual_tags.get(item.get("name", ""))
            item["creativeBucket"] = manual_tag.get("bucket") if manual_tag and manual_tag.get("bucket") else self._creative_bucket_for_item(item)
            if manual_tag:
                item["manualTag"] = manual_tag

        category_counts = Counter(self._category_for_mime(item.get("mimeType", "")) for item in files)
        bucket_counts = Counter(item["creativeBucket"] for item in files)
        lines = [
            "Google Drive asset inventory:",
            "",
            f"Total assets: {len(files)}",
            "Asset mix:",
            *[f"- {category}: {count}" for category, count in sorted(category_counts.items())],
            "",
            "Raw Content creative sorting:",
            *[
                f"- {bucket}: {bucket_counts.get(bucket, 0)} assets"
                for bucket in CREATIVE_BUCKET_ORDER
                if bucket_counts.get(bucket, 0)
            ],
            "",
            *self._photoshoot_summary_lines(files),
            "",
            "Creative use map:",
            "- Store Products: product-specific photos from the Products folder. Use these as the approved garment/product inventory for concepts and product selections.",
            "- First Post Inspiration: human-built first-post references. Treat these as soft style and sequencing cues, not hard rules.",
            "- Shoot Photos: all JRR series files. Use these as main campaign shots for product posts, launches, and polished carousels.",
            "- Photoshoot / Campaign: newer editorial or campaign shoot folders. Use these as premium feed anchors, model/body proof, and visual pacing pieces.",
            "- Process / Studio: behind-the-scenes HEIC files. Use these for studio/process posts and making-of context.",
            "- Design Assets: Adrift painting, 4DRFT design files, and related source graphics. Use these for source-work, design-system, and transformation posts.",
            "- Video: MOV files. Use these for Reel concepts and motion-led storyboards.",
            "",
            "Files by creative bucket:",
        ]
        for bucket in CREATIVE_BUCKET_ORDER:
            bucket_files = sorted(
                [item for item in files if item.get("creativeBucket") == bucket],
                key=lambda item: item.get("name", "").lower(),
            )
            if not bucket_files:
                continue

            limit = self._bucket_display_limit(bucket)
            lines.extend(["", f"### {bucket}"])
            for item in bucket_files[:limit]:
                location = item.get("folderPath", "root")
                size = self._format_size(item.get("size"))
                lines.append(
                    f"- {item['name']} | {self._category_for_mime(item.get('mimeType', ''))} | "
                    f"{item['mimeType']} | {size} | {location} | modified {item.get('modifiedTime', 'unknown')}"
                    f"{self._manual_tag_suffix(item)}"
                )

            if len(bucket_files) > limit:
                lines.append(f"- {len(bucket_files) - limit} additional {bucket} assets not shown in prompt context.")

        return AssetInventory(enabled=True, summary="\n".join(lines), files=files)

    def download_image_assets(self, destination: Path, limit: int) -> list[Path]:
        if not self.enabled:
            return []

        if self._missing_auth_message():
            return []

        service = self._build_service()
        files = [
            item
            for item in self._list_files(service, self._folder_id())
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

    def list_raw_assets(self) -> list[dict]:
        if not self.enabled or self._missing_auth_message():
            return []

        files = self._list_files(self._build_service(), self._folder_id())
        manual_tags = self._manual_asset_tags()
        for item in files:
            manual_tag = manual_tags.get(item.get("name", ""))
            item["creativeBucket"] = manual_tag.get("bucket") if manual_tag and manual_tag.get("bucket") else self._creative_bucket_for_item(item)
            item["manualTag"] = manual_tag or {}
            item["category"] = self._category_for_mime(item.get("mimeType", ""))
            item["sizeLabel"] = self._format_size(item.get("size"))
            enrich_asset_design_roles(item)
        return sorted(
            files,
            key=lambda item: (
                self._creative_bucket_rank(item.get("creativeBucket", "Other")),
                item.get("name", "").lower(),
            ),
        )

    def download_drive_file(self, file_id: str, destination: Path) -> Path:
        service = self._build_service()
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = service.files().get_media(fileId=file_id)
        with FileIO(destination, "wb") as handle:
            downloader = self._media_downloader(handle, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return destination

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
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        token_path = Path(GOOGLE_OAUTH_TOKEN_FILE)
        credentials = None

        if token_path.exists():
            credentials = Credentials.from_authorized_user_file(token_path, DRIVE_READONLY_SCOPES)

        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except RefreshError:
                credentials = None

        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_OAUTH_CLIENT_FILE, DRIVE_READONLY_SCOPES)
            credentials = flow.run_local_server(port=0)
            token_path.write_text(credentials.to_json(), encoding="utf-8")

        return credentials

    def _list_files(self, service, folder_id: str, folder_path: str = "root") -> list[dict]:
        query = f"'{folder_id}' in parents and trashed = false"
        expanded: list[dict] = []
        page_token = None

        while True:
            results = (
                service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink, thumbnailLink)",
                    orderBy="folder,name",
                    pageSize=1000,
                    pageToken=page_token,
                )
                .execute()
            )
            files = results.get("files", [])

            for item in files:
                if item.get("mimeType") == "application/vnd.google-apps.folder":
                    child_path = f"{folder_path}/{item['name']}"
                    expanded.extend(self._list_files(service, item["id"], child_path))
                else:
                    item["folderPath"] = folder_path
                    expanded.append(item)

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        return expanded

    def _folder_id(self) -> str:
        raw = GOOGLE_DRIVE_ROOT_FOLDER_ID.strip()
        if raw.startswith("http"):
            parsed = urlparse(raw)
            parts = [part for part in parsed.path.split("/") if part]
            if "folders" in parts:
                index = parts.index("folders")
                if len(parts) > index + 1:
                    return parts[index + 1]
            query = parse_qs(parsed.query)
            if "id" in query and query["id"]:
                return query["id"][0]
        return raw

    def _media_downloader(self, handle, request):
        from googleapiclient.http import MediaIoBaseDownload

        return MediaIoBaseDownload(handle, request)

    def _suffix_for_mime(self, mime_type: str) -> str:
        return {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/heic": ".heic",
            "image/heif": ".heif",
            "video/quicktime": ".mov",
            "video/mp4": ".mp4",
        }.get(mime_type, ".img")

    def _category_for_mime(self, mime_type: str) -> str:
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("video/"):
            return "video"
        if mime_type.startswith("audio/"):
            return "audio"
        if mime_type in {"application/pdf", "text/plain"} or mime_type.startswith("application/vnd.google-apps"):
            return "document"
        return "other"

    def _creative_bucket_for_item(self, item: dict) -> str:
        name = item.get("name", "")
        mime_type = item.get("mimeType", "")
        stem = Path(name).stem.lower()
        suffix = Path(name).suffix.lower()

        if mime_type.startswith("video/") or suffix in {".mov", ".mp4", ".m4v"}:
            return "Video"

        folder_path = item.get("folderPath", "").lower()
        normalized_folder = folder_path.replace("\\", "/")
        if (
            "first post" in normalized_folder
            or "first-post" in normalized_folder
            or "first_post" in normalized_folder
            or ("inspiration" in normalized_folder and "post" in normalized_folder)
        ):
            return "First Post Inspiration"

        if "/products/" in folder_path or folder_path.endswith("/products"):
            return "Store Products"

        if "photoshoot" in normalized_folder or "campaign" in normalized_folder:
            return "Photoshoot / Campaign"

        if stem.startswith("jrr"):
            return "Shoot Photos"

        if suffix in {".heic", ".heif"}:
            return "Process / Studio"

        design_terms = ("adrift", "4drft", "design", "painting", "background", "branches")
        if any(term in stem for term in design_terms):
            return "Design Assets"

        return "Other"

    def _creative_bucket_rank(self, bucket: str) -> int:
        try:
            return CREATIVE_BUCKET_ORDER.index(bucket)
        except ValueError:
            return len(CREATIVE_BUCKET_ORDER)

    def _bucket_display_limit(self, bucket: str) -> int:
        return {
            "First Post Inspiration": 80,
            "Store Products": 80,
            "Shoot Photos": 40,
            "Photoshoot / Campaign": 80,
            "Process / Studio": 35,
            "Design Assets": 40,
            "Video": 40,
            "Other": 20,
        }.get(bucket, 20)

    def _photoshoot_summary_lines(self, files: list[dict]) -> list[str]:
        photoshoot_files = [item for item in files if item.get("creativeBucket") == "Photoshoot / Campaign"]
        if not photoshoot_files:
            return ["Photoshoot / Campaign summary:", "- No photoshoot campaign assets found yet."]
        folders = Counter(item.get("folderPath", "root") for item in photoshoot_files)
        lines = ["Photoshoot / Campaign summary:"]
        for folder, count in sorted(folders.items()):
            lines.append(f"- {folder}: {count} campaign assets")
        return lines

    def _manual_asset_tags(self) -> dict[str, dict]:
        path = ROOT_DIR / "brand_context" / "asset_tags.csv"
        if not path.exists():
            return {}

        tags: dict[str, dict] = {}
        with path.open(encoding="utf-8", newline="") as handle:
            rows = (line for line in handle if not line.lstrip().startswith("#"))
            for row in csv.DictReader(rows):
                filename = (row.get("filename") or "").strip()
                if not filename:
                    continue
                tags[filename] = {
                    "bucket": (row.get("bucket") or "").strip(),
                    "priority": (row.get("priority") or "").strip(),
                    "notes": (row.get("notes") or "").strip(),
                    "roles": (row.get("roles") or "").strip(),
                }
        return tags

    def _manual_tag_suffix(self, item: dict) -> str:
        manual_tag = item.get("manualTag")
        if not manual_tag:
            return ""

        details = []
        if manual_tag.get("priority"):
            details.append(f"manual priority {manual_tag['priority']}")
        if manual_tag.get("notes"):
            details.append(manual_tag["notes"])

        return f" | {'; '.join(details)}" if details else " | manual tag"

    def _format_size(self, raw_size: str | None) -> str:
        if not raw_size:
            return "unknown size"

        size = int(raw_size)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024

        return f"{raw_size} B"
