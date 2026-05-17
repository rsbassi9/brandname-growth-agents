from pathlib import Path
import os

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
BRAND_CONTEXT_DIR = ROOT_DIR / "brand_context"
AGENT_INSTRUCTIONS_DIR = ROOT_DIR / "agent_instructions"
OUTPUTS_DIR = ROOT_DIR / "outputs"
PRODUCT_INVENTORY_DIR = BRAND_CONTEXT_DIR / "product_inventory"

load_dotenv(ROOT_DIR / ".env", override=True)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
BRAND_WEBSITE_URL = os.getenv("BRAND_WEBSITE_URL", "https://www.brandnamedesign.co/")
GOOGLE_DRIVE_ENABLED = os.getenv("GOOGLE_DRIVE_ENABLED", "false").lower() == "true"
GOOGLE_DRIVE_ROOT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "")
GOOGLE_AUTH_MODE = os.getenv("GOOGLE_AUTH_MODE", "oauth").lower()
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
GOOGLE_OAUTH_CLIENT_FILE = os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "oauth_client.json")
GOOGLE_OAUTH_TOKEN_FILE = os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "token.json")
VISUAL_OUTPUT_ENABLED = os.getenv("VISUAL_OUTPUT_ENABLED", "false").lower() == "true"
VISUAL_ASSET_LIMIT = int(os.getenv("VISUAL_ASSET_LIMIT", "12"))
IMAGE_CONCEPTS_ENABLED = os.getenv("IMAGE_CONCEPTS_ENABLED", "false").lower() == "true"
IMAGE_CONCEPT_COUNT = int(os.getenv("IMAGE_CONCEPT_COUNT", "3"))
IMAGE_CONCEPT_MODEL = os.getenv("IMAGE_CONCEPT_MODEL", "gpt-image-1")
IMAGE_CONCEPT_SIZE = os.getenv("IMAGE_CONCEPT_SIZE", "1024x1536")
IMAGE_CONCEPT_QUALITY = os.getenv("IMAGE_CONCEPT_QUALITY", "medium")
SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN", "")
SHOPIFY_ADMIN_ACCESS_TOKEN = os.getenv("SHOPIFY_ADMIN_ACCESS_TOKEN", "")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2025-04")
SHOPIFY_WRITE_ENABLED = os.getenv("SHOPIFY_WRITE_ENABLED", "false").lower() == "true"
