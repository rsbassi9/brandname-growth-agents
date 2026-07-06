# Key Rotation Checklist (manual — do this yourself)

The credentials below were present in the working tree during development and
must be treated as potentially exposed. Rotate them manually. No key material
is (or should ever be) included in this document or committed to git.

## 1. OpenAI API key (`.env`)

- [ ] Go to https://platform.openai.com → API keys.
- [ ] Revoke the current key.
- [ ] Create a new key and update `OPENAI_API_KEY` in the local `.env` file.
- [ ] Confirm `.env` is still listed in `.gitignore` and never committed.

## 2. Google OAuth client secret (`oauth_client.json`)

- [ ] Go to https://console.cloud.google.com → APIs & Services → Credentials.
- [ ] Delete (or reset the secret of) the existing OAuth 2.0 client.
- [ ] Create a new OAuth client and download the new `oauth_client.json`
      into the repo root, replacing the old file.
- [ ] Confirm `oauth_client.json` is still gitignored.

## 3. Google OAuth token (`token.json`)

- [ ] Delete the local `token.json`.
- [ ] Re-run the Drive authentication flow to re-issue a fresh `token.json`
      (it is created automatically on the next authorized run).
- [ ] Confirm `token.json` is still gitignored.

All three steps must be performed manually at platform.openai.com /
console.cloud.google.com — nothing in this repo can rotate them for you.
