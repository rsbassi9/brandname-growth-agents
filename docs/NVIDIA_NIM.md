# Cheap/local text models: NVIDIA NIM and Ollama

All OpenAI-SDK calls go through one wrapper (`app/services/openai_client.py`)
that honors `BRAND_OPENAI_BASE_URL` + `BRAND_OPENAI_API_KEY`, so any
OpenAI-compatible endpoint works without code changes.

## NVIDIA NIM (free tier / cheap hosted)

1. Create an API key at https://build.nvidia.com (NVIDIA NIM).
2. In `.env`:

       BRAND_OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
       BRAND_OPENAI_API_KEY=nvapi-...
       BRAND_MODEL_DEFAULT=meta/llama-3.1-8b-instruct

## Ollama (fully local, free)

1. Install from https://ollama.com and run `ollama pull llama3.1`.
2. In `.env`:

       BRAND_OPENAI_BASE_URL=http://localhost:11434/v1
       BRAND_OPENAI_API_KEY=ollama
       BRAND_MODEL_DEFAULT=llama3.1

## Two-tier model policy

`BRAND_MODEL_DEFAULT` (cheap) is used everywhere by default.
`BRAND_MODEL_PREMIUM` (optional) is only used when a generation explicitly
opts in ("Use premium model" toggle); unset means the default tier is used.
