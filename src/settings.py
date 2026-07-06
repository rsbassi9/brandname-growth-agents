from pathlib import Path
import os
import shutil

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=False)

DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT_DIR))).resolve()
BRAND_CONTEXT_DIR = ROOT_DIR / "brand_context"
AGENT_INSTRUCTIONS_DIR = ROOT_DIR / "agent_instructions"
MEMORY_DIR = DATA_DIR / "memory"
OUTPUTS_DIR = DATA_DIR / "outputs"
PRODUCT_INVENTORY_DIR = DATA_DIR / "brand_context" / "product_inventory"

def _seed_persistent_dir(source: Path, destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        return
    if source.exists():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        destination.mkdir(parents=True, exist_ok=True)


if DATA_DIR != ROOT_DIR:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _seed_persistent_dir(ROOT_DIR / "memory", MEMORY_DIR)
    _seed_persistent_dir(ROOT_DIR / "outputs", OUTPUTS_DIR)
    _seed_persistent_dir(BRAND_CONTEXT_DIR / "product_inventory", PRODUCT_INVENTORY_DIR)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
LOCAL_ONLY_AGENT_RUNS = os.getenv("LOCAL_ONLY_AGENT_RUNS", "false").lower() == "true"
BRAND_WEBSITE_URL = os.getenv("BRAND_WEBSITE_URL", "https://www.brandnamedesign.co/")
GOOGLE_DRIVE_ENABLED = os.getenv("GOOGLE_DRIVE_ENABLED", "false").lower() == "true"
GOOGLE_DRIVE_ROOT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "")
GOOGLE_AUTH_MODE = os.getenv("GOOGLE_AUTH_MODE", "oauth").lower()
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
GOOGLE_OAUTH_CLIENT_FILE = os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "oauth_client.json")
GOOGLE_OAUTH_TOKEN_FILE = os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "token.json")
VISUAL_OUTPUT_ENABLED = os.getenv("VISUAL_OUTPUT_ENABLED", "false").lower() == "true"
VISUAL_ASSET_LIMIT = int(os.getenv("VISUAL_ASSET_LIMIT", "12"))
AI_IMAGE_GENERATION_ENABLED = os.getenv("AI_IMAGE_GENERATION_ENABLED", "false").lower() == "true"
IMAGE_CONCEPTS_ENABLED = os.getenv("IMAGE_CONCEPTS_ENABLED", "false").lower() == "true"
IMAGE_CONCEPT_COUNT = int(os.getenv("IMAGE_CONCEPT_COUNT", "3"))
IMAGE_CONCEPT_MODEL = os.getenv("IMAGE_CONCEPT_MODEL", "gpt-image-1")
IMAGE_CONCEPT_SIZE = os.getenv("IMAGE_CONCEPT_SIZE", "1024x1536")
IMAGE_CONCEPT_QUALITY = os.getenv("IMAGE_CONCEPT_QUALITY", "medium")
SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN", "")
SHOPIFY_ADMIN_ACCESS_TOKEN = os.getenv("SHOPIFY_ADMIN_ACCESS_TOKEN", "")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2025-04")
SHOPIFY_WRITE_ENABLED = os.getenv("SHOPIFY_WRITE_ENABLED", "false").lower() == "true"
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "brandname")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")
DASHBOARD_AUTH_ENABLED = os.getenv("DASHBOARD_AUTH_ENABLED", "false").lower() == "true"