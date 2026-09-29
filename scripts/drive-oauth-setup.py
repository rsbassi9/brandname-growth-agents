#!/usr/bin/env python3
"""Explicit owner login on a laptop, never invoked by an unattended worker."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.drive_auth import save_token  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client_json", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists():
        parser.error("Output already exists; choose a new filename to preserve your existing token.")
    if not output.parent.is_dir():
        parser.error("Output directory must already exist.")
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(
        args.client_json.expanduser(), ["https://www.googleapis.com/auth/drive.readonly"]
    )
    credentials = flow.run_local_server(
        host="127.0.0.1", port=0, prompt="consent", access_type="offline",
        authorization_prompt_message="Opening Google Drive read-only consent in your browser...",
        timeout_seconds=300,
    )
    if not credentials.refresh_token:
        raise RuntimeError("Google did not grant offline access; no token was saved.")
    save_token(output, credentials.to_json())
    print(f"Authentication complete. Owner-only token saved at {output}; keep its contents private.")


if __name__ == "__main__":
    main()
