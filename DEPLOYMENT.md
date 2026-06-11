# Deployment

This MVP deploys as two Python web services:

- `developer-copilot-api`: FastAPI backend, data access, Twilio webhook, `/ask`
- `developer-copilot-dashboard`: Streamlit dashboard for judges and demo users

No Docker is required.

## Recommended Platform

Use Render for the hackathon demo because it can host both Python services from the same GitHub repo.

## Save To GitHub

Do not commit `.env`, `.venv`, `.next`, `node_modules`, or `storage`.

The important app files are:

- `developer_copilot/`
- `lead_analytics/`
- `frontend/streamlit_app.py`
- `data/*.csv`
- `data/snowflake_seed.sql`
- `scripts/`
- `tests/`
- `requirements.txt`
- `render.yaml`
- `README.md`
- `.env.example`

This machine may not have the system `git` command available. In that case, set these values in `.env` and run the API publisher:

```bash
GITHUB_TOKEN=
GITHUB_REPO_NAME=developer-copilot-mvp
GITHUB_PRIVATE=true
```

Then:

```bash
python scripts/publish_github.py
```

The script publishes only the deployable app files and skips local secrets/caches.

## Deploy With Render API

Set a Render API key in `.env`:

```bash
RENDER_API_KEY=
```

If your Render account has multiple workspaces, also set:

```bash
RENDER_OWNER_ID=
```

Then run:

```bash
python scripts/deploy_render.py
```

The script creates or reuses:

- `developer-copilot-api`
- `developer-copilot-dashboard`

It sets `BASE_URL` on the backend and `API_BASE_URL` on the dashboard.

## Render Setup

Create two Render Web Services from the same GitHub repo.

### Backend

Name:

```text
developer-copilot-api
```

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
python -m uvicorn developer_copilot.main:app --host 0.0.0.0 --port $PORT
```

Required env vars for mock-data demo:

```bash
ENVIRONMENT=production
DATA_SOURCE=mock
FALLBACK_TO_MOCK=true
TARGET_DEVELOPER_ID=101
BASE_URL=https://your-api-service.onrender.com
TWILIO_SEND_AUDIO=false
```

Twilio env vars:

```bash
TWILIO_ENABLED=true
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

OpenAI is optional but recommended:

```bash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

Snowflake is optional. Keep `DATA_SOURCE=mock` for the fastest demo.

### Dashboard

Name:

```text
developer-copilot-dashboard
```

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
streamlit run frontend/streamlit_app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true --browser.gatherUsageStats false
```

Env var:

```bash
API_BASE_URL=https://your-api-service.onrender.com
```

## Twilio Webhook

After the backend is live, set the Twilio WhatsApp inbound webhook to:

```text
https://your-api-service.onrender.com/twilio/whatsapp/webhook
```

Use HTTP `POST`.

## Demo URL

Share the dashboard URL with judges:

```text
https://your-dashboard-service.onrender.com
```

The dashboard co-pilot talks to the deployed backend through `API_BASE_URL`.
