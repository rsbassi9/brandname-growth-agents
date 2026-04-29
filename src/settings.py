from pathlib import Path
import os

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
BRAND_CONTEXT_DIR = ROOT_DIR / "brand_context"
AGENT_INSTRUCTIONS_DIR = ROOT_DIR / "agent_instructions"
OUTPUTS_DIR = ROOT_DIR / "outputs"

load_dotenv(ROOT_DIR / ".env", override=True)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
BRAND_WEBSITE_URL = os.getenv("BRAND_WEBSITE_URL", "https://www.brandnamedesign.co/")
GOOGLE_DRIVE_ENABLED = os.getenv("GOOGLE_DRIVE_ENABLED", "false").lower() == "true"
GOOGLE_DRIVE_ROOT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
VISUAL_OUTPUT_ENABLED = os.getenv("VISUAL_OUTPUT_ENABLED", "true").lower() == "true"
VISUAL_ASSET_LIMIT = int(os.getenv("VISUAL_ASSET_LIMIT", "12"))
