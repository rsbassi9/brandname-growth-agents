# Brand Name Growth Agents

OpenAI-first marketing agent system for Brand Name Design.

The MVP runs a daily review workflow:
- generates content ideas
- drafts captions, short video scripts, and carousel concepts
- audits the website for SEO opportunities
- summarizes analytics constraints or learnings
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

Add your API key to `.env`:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.4-mini
```

Run the workflow:

```powershell
python -m src.orchestrator
```

Outputs are written to:

```text
outputs/content_ideas
outputs/content_drafts
outputs/seo
outputs/analytics
outputs/daily_reports
```

## Google Drive

Google Drive is optional for the MVP.

To enable it:
1. Create a Google Cloud project.
2. Enable the Google Drive API.
3. Create a service account.
4. Download the service account JSON as `credentials.json`.
5. Share the Brand Name Design Drive folder with the service account email.
6. Set:

```text
GOOGLE_DRIVE_ENABLED=true
GOOGLE_DRIVE_ROOT_FOLDER_ID=your_folder_id
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
```

The first Drive pass creates an asset inventory summary from the configured folder. It does not upload or move files yet.

## GitHub Actions

The workflow in `.github/workflows/daily-growth.yml` runs every day at 8:00 AM Vancouver time during standard time equivalent scheduling.

Add these repo settings:
- Secret: `OPENAI_API_KEY`
- Optional secret: `GOOGLE_DRIVE_ROOT_FOLDER_ID`
- Optional variable: `OPENAI_MODEL`
- Optional variable: `GOOGLE_DRIVE_ENABLED`

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
src/
scripts/
```

## Next Build Step

Add Drive upload support so generated markdown files can be mirrored into:

```text
/Brand Name Design/02_Daily Agent Outputs
/Brand Name Design/03_Drafts for Review
```
