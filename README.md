# Brand Name Growth Agents

OpenAI-first marketing agent system for Brand Name Design.

The MVP runs a daily review workflow:
- inventories raw Google Drive assets when enabled
- generates content ideas
- drafts captions, short video scripts, and carousel concepts
- renders a draft Instagram carousel as PNG slides
- generates three OpenAI image concept directions for visual exploration
- audits the website for SEO opportunities
- summarizes analytics constraints or learnings
- produces Phase 2 ad readiness notes without recommending spend unless evidence exists
- saves review-ready markdown outputs

It does not auto-publish content.

## Stack

- Python
- OpenAI Agents SDK
- Optional Google Drive API
- GitHub Actions daily schedule

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

If Windows blocks a global install, use:

```powershell
python -m pip install --user -r requirements.txt
```

Add your API key to `.env`:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.4-mini
```

Run the workflow:

```powershell
python -m src.orchestrator
```

Run the review dashboard:

```powershell
python -m uvicorn src.dashboard:app --reload --port 8765
```

Then open:

```text
http://127.0.0.1:8765
```

If you see an `insufficient_quota` error, the code reached OpenAI successfully. Fix billing, credits, or usage limits in the OpenAI platform project tied to your API key, then rerun the same command.

Outputs are written to:

```text
outputs/content_ideas
outputs/content_drafts
outputs/seo
outputs/analytics
outputs/daily_reports
outputs/ad_concepts
outputs/visual_content
outputs/image_concepts
outputs/asset_inventory
```

## Dashboard + Learning Loop

The local dashboard lets you:
- review daily generated reports, drafts, SEO notes, and visual slides
- rate outputs from 1 to 5
- leave comments and improvement requests
- run the agents manually from the browser

Feedback is stored in:

```text
memory/feedback.jsonl
```

Every future agent run reads recent feedback and uses it as learning context.

## Hosted Read/Write Dashboard

For access from anywhere, deploy the FastAPI dashboard as a hosted web service. GitHub Pages can only host the read-only static mirror; it cannot run the Python backend, save feedback, read Drive, or run agents.

This repo includes a Render blueprint:

```text
render.yaml
```

Render setup:
1. Push this repo to GitHub.
2. In Render, create a new Blueprint from this repo.
3. Use the `render.yaml` file at the repo root.
4. Set these required secrets:

```text
OPENAI_API_KEY=your_openai_api_key
DASHBOARD_PASSWORD=a_long_private_password
```

5. Keep `DASHBOARD_AUTH_ENABLED=true` in Render.
6. Deploy the service.

The hosted app uses:

```text
uvicorn src.dashboard:app --host 0.0.0.0 --port $PORT
```

The blueprint mounts a persistent disk at:

```text
/var/data
```

and sets:

```text
DATA_DIR=/var/data
```

That keeps generated outputs, dashboard memory, feedback, calendar edits, and uploaded product references across redeploys. On first boot, the app seeds `/var/data/memory`, `/var/data/outputs`, and `/var/data/brand_context/product_inventory` from the repo if the disk is empty.

Optional hosted settings:

```text
GOOGLE_DRIVE_ENABLED=true
GOOGLE_DRIVE_ROOT_FOLDER_ID=your_folder_id
GOOGLE_AUTH_MODE=service_account
GOOGLE_APPLICATION_CREDENTIALS=/var/data/credentials.json
```

For OAuth on a hosted service, place `oauth_client.json` and `token.json` on the persistent disk or use a service account. The Drive folder must be shared with the authenticating Google identity.

## Google Drive

Google Drive is optional for the MVP.

Use it when you want the agents to read a Drive folder of raw assets before creating content ideas. The workflow saves a review-ready asset inventory to:

```text
outputs/asset_inventory
```

To enable it with user OAuth, which works well for a local starter repo:
1. Create a Google Cloud project.
2. Enable the Google Drive API.
3. Go to **APIs & Services -> OAuth consent screen** and configure the app for your Google account.
4. Go to **APIs & Services -> Credentials**.
5. Create an **OAuth client ID**.
6. Choose **Desktop app**.
7. Download the JSON file as `oauth_client.json`.
8. Put it in the repo root.
9. Copy your raw content folder ID from the Google Drive URL. In a URL like `https://drive.google.com/drive/folders/abc123`, use `abc123`.
10. Set:

```text
GOOGLE_DRIVE_ENABLED=true
GOOGLE_DRIVE_ROOT_FOLDER_ID=your_folder_id
GOOGLE_AUTH_MODE=oauth
GOOGLE_OAUTH_CLIENT_FILE=oauth_client.json
GOOGLE_OAUTH_TOKEN_FILE=token.json
```

The first run opens a Google sign-in browser window and creates `token.json`. Future runs reuse `token.json`.

If you are using a Google project that still allows service account keys, set `GOOGLE_AUTH_MODE=service_account` and use `GOOGLE_APPLICATION_CREDENTIALS=credentials.json`.

For GitHub Actions with OAuth, create `token.json` locally first, then store its contents as a GitHub secret and write it during the workflow, or use a service account if your Google Workspace policy allows it. The Drive folder must be shared with whichever Google identity is authenticating.

The Drive pass creates a recursive asset inventory summary from the configured folder before content ideas are generated. The strategist is instructed to reference available assets and request missing assets instead of inventing them. When `VISUAL_OUTPUT_ENABLED=true`, image files from the Drive folder are downloaded into `.cache/drive_assets` and used as source material for rendered PNG carousel slides.

## GitHub Actions

The workflow in `.github/workflows/daily-growth.yml` runs every day at 8:00 AM Vancouver time during standard time equivalent scheduling.

Add these repo settings:
- Secret: `OPENAI_API_KEY`
- Optional secret: `GOOGLE_DRIVE_ROOT_FOLDER_ID`
- Optional secret: `GOOGLE_OAUTH_CLIENT_JSON` if you want CI to authenticate with OAuth
- Optional secret: `GOOGLE_OAUTH_TOKEN_JSON` if you want CI to authenticate with OAuth
- Optional secret: `GOOGLE_APPLICATION_CREDENTIALS_JSON` if you want CI to authenticate with a service account
- Optional variable: `OPENAI_MODEL`
- Optional variable: `LOCAL_ONLY_AGENT_RUNS`
- Optional variable: `GOOGLE_DRIVE_ENABLED`
- Optional variable: `GOOGLE_AUTH_MODE`
- Optional variable: `VISUAL_OUTPUT_ENABLED`
- Optional variable: `VISUAL_ASSET_LIMIT`
- Optional variable: `AI_IMAGE_GENERATION_ENABLED`
- Optional variable: `IMAGE_CONCEPTS_ENABLED`

## Project Folders

```text
brand_context/
agent_instructions/
outputs/content_ideas/
outputs/content_drafts/
outputs/seo/
outputs/analytics/
outputs/daily_reports/
outputs/ad_concepts/
outputs/asset_inventory/
outputs/visual_content/
src/
scripts/
```

## Next Build Step

Add Drive upload support so generated markdown files can be mirrored into:

```text
/Brand Name Design/02_Daily Agent Outputs
/Brand Name Design/03_Drafts for Review
```

## Visual Content Outputs

The visual pipeline produces:
- a JSON design brief
- a markdown visual brief
- PNG carousel slides sized for Instagram portrait posts

Outputs are saved under:

```text
outputs/visual_content/
```

If Google Drive is disabled or no images are available, the renderer creates text-first placeholder slides so the daily run still completes.

## OpenAI Image Concepts

Image generation is opt-in. Keep `AI_IMAGE_GENERATION_ENABLED=false` when you want post generators and dashboard tools to run from Drive/source assets without spending OpenAI image credits.

When both `AI_IMAGE_GENERATION_ENABLED=true` and `IMAGE_CONCEPTS_ENABLED=true`, each run asks the Visual Designer agent for three image briefs and generates three OpenAI image concepts.

These are exploratory source visuals, not final posts. The prompts intentionally ask for no embedded text so the dashboard or renderer can apply brand typography consistently.

Outputs are saved under:

```text
outputs/image_concepts/
```

## Local-Only Runs

Set `LOCAL_ONLY_AGENT_RUNS=true` to make Run Today write deterministic markdown outputs from the current Drive asset inventory and brand rules without calling OpenAI for text or images. This is useful when API quota is unavailable or when you want a review-ready asset/rules pass only.

Useful settings:

```text
AI_IMAGE_GENERATION_ENABLED=false
IMAGE_CONCEPTS_ENABLED=false
IMAGE_CONCEPT_COUNT=3
IMAGE_CONCEPT_MODEL=gpt-image-1
IMAGE_CONCEPT_SIZE=1024x1536
IMAGE_CONCEPT_QUALITY=medium
```
