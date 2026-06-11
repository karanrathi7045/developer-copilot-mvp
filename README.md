# Developer Co-pilot

Developer Co-pilot is a hackathon MVP for daily developer sales briefings. It reads project data from Snowflake or mock CSV tables, reasons over pipeline health with OpenAI, sends WhatsApp updates through Twilio, and exposes a developer-facing Streamlit dashboard with a bottom-right co-pilot chatbot.

Mock CSV is the default, so the app runs without vendor credentials.

## Features

- FastAPI backend with `/ask` and `/generate-action`
- Daily summary with top objection, conversion trend, inactive CPs, inventory opportunity, and recommendation
- Twilio WhatsApp text dispatch when configured
- Twilio inbound WhatsApp Q&A webhook
- APScheduler daily 8 AM briefing job
- Streamlit developer dashboard with floating Ask Co-pilot chatbot
- Six normalized mock tables with 100 rows each
- Snowflake connector path with CSV fallback and seed script
- Render deployment config without Docker

## Project Structure

```text
developer_copilot/       FastAPI app, integrations, scheduler, briefing flow
lead_analytics/          Existing CSV analytics core
frontend/streamlit_app.py
data/leads.csv
data/developers.csv
data/projects.csv
data/inventory.csv
data/bookings.csv
data/channel_partner.csv
data/snowflake_seed.sql
scripts/generate_mock_tables.py
scripts/load_snowflake_seed.py
tests/
```

## Mock Tables

Each mock table has 100 data rows:

- `DEVELOPERS`: `ID`, `DEVELOPER_NAME`, `COUNTRY_CODE`, `DEVELOPER_PHONE`, `CATEGORY`
- `LEADS`: `ID`, `NAME`, `STATUS`, `PROJECT_ID`
- `PROJECTS`: `ID`, `NAME`, `DEVELOPER_ID`, `STAGE`
- `INVENTORY`: `ID`, `PROJECT_ID`, `CONFIGURATION`, `TOTAL_UNITS`, `AVAILABLE_UNITS`
- `BOOKINGS`: `ID`, `LEAD_ID`, `CONFIGURATION`, `BOOKING_DATE`, `AGREEMENT_VALUE`, `BROKERAGE_AMOUNT`
- `CHANNEL_PARTNER`: `ID`, `CP_NAME`, `OPERATION_LOCALITY`, `PROJECTS_WORKING_ON`

`OPERATION_LOCALITY` and `PROJECTS_WORKING_ON` are stored as JSON arrays in CSV and as `ARRAY` columns in Snowflake.

The demo developer is seeded as:

```text
101, Karan Rathi, 91, 7045706453, A
```

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

If your machine exposes Python as a different command, use that command for the first line.

## Run Locally

Start the backend:

```bash
uvicorn developer_copilot.main:app --reload
```

Start the dashboard in a second terminal:

```bash
streamlit run frontend/streamlit_app.py
```

Open:

- Backend: [http://localhost:8000/docs](http://localhost:8000/docs)
- Dashboard: [http://localhost:8501](http://localhost:8501)

## Environment Variables

Core:

```bash
DATA_SOURCE=mock
FALLBACK_TO_MOCK=true
BASE_URL=http://localhost:8000
TARGET_DEVELOPER_ID=101
DEVELOPERS_CSV_PATH=data/developers.csv
LEADS_CSV_PATH=data/leads.csv
PROJECTS_CSV_PATH=data/projects.csv
INVENTORY_CSV_PATH=data/inventory.csv
BOOKINGS_CSV_PATH=data/bookings.csv
CHANNEL_PARTNER_CSV_PATH=data/channel_partner.csv
SCHEDULER_ENABLED=true
SCHEDULER_TIMEZONE=Asia/Kolkata
SCHEDULER_HOUR=8
SCHEDULER_MINUTE=0
```

Snowflake:

```bash
SNOWFLAKE_ENABLED=true
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_ROLE=
SNOWFLAKE_WAREHOUSE=
SNOWFLAKE_DATABASE=
SNOWFLAKE_SCHEMA=
SNOWFLAKE_DEVELOPERS_TABLE=DEVELOPERS
SNOWFLAKE_LEADS_TABLE=LEADS
SNOWFLAKE_PROJECTS_TABLE=PROJECTS
SNOWFLAKE_INVENTORY_TABLE=INVENTORY
SNOWFLAKE_BOOKINGS_TABLE=BOOKINGS
SNOWFLAKE_CHANNEL_PARTNER_TABLE=CHANNEL_PARTNER
```

Load the mock tables into Snowflake after filling the Snowflake env vars:

```bash
python scripts/load_snowflake_seed.py
```

You can also run `data/snowflake_seed.sql` directly in Snowflake.

OpenAI:

```bash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_TRANSCRIPTION_MODEL=whisper-1
OPENAI_TEMPERATURE=0.2
```

ElevenLabs:

```bash
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
```

Twilio WhatsApp:

```bash
TWILIO_ENABLED=true
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_MESSAGING_SERVICE_SID=
TWILIO_CONTENT_SID=
TWILIO_STATUS_CALLBACK=
TWILIO_SEND_AUDIO=false
```

For the Twilio Sandbox, the developer WhatsApp number must join the sandbox first. If your WhatsApp window requires approved outbound templates, set `TWILIO_CONTENT_SID`; otherwise the app sends the briefing as a regular `Body` message.

Voice mode is not recommended for the hackathon deployment. Keep `TWILIO_SEND_AUDIO=false` for a stable demo.

Optional voice mode:

- Outgoing audio briefings need `ELEVENLABS_API_KEY`, `TWILIO_SEND_AUDIO=true`, and `BASE_URL` set to your public backend URL.
- Incoming developer voice notes need `OPENAI_API_KEY` for transcription.
- If `BASE_URL` is still `localhost`, Twilio can receive the text brief but cannot fetch the generated audio file.

Inbound developer questions use this webhook:

```text
POST /twilio/whatsapp/webhook
```

In the Twilio Sandbox page, set **When a message comes in** to your public backend URL:

```text
https://your-public-url/twilio/whatsapp/webhook
```

Twilio cannot reach `127.0.0.1` directly, so local demos need a public tunnel such as LocalTunnel or ngrok pointing to the FastAPI port. Deployed demos should use the hosted backend URL.

## Deploy

The recommended hackathon deployment is two Python web services, no Docker:

- FastAPI backend: `python -m uvicorn developer_copilot.main:app --host 0.0.0.0 --port $PORT`
- Streamlit dashboard: `streamlit run frontend/streamlit_app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true --browser.gatherUsageStats false`

See [DEPLOYMENT.md](DEPLOYMENT.md) and [render.yaml](render.yaml).

## API Examples

Generate the daily briefing:

```bash
curl -X POST http://localhost:8000/briefing/daily \
  -H "Content-Type: application/json" \
  -d '{"send_whatsapp": false}'
```

Ask Co-pilot:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the top objection and what should we do today?"}'
```

Generate a CP action:

```bash
curl -X POST http://localhost:8000/generate-action \
  -H "Content-Type: application/json" \
  -d '{"target": "NorthStar Realty", "action_type": "cp_message", "tone": "confident"}'
```

Send through WhatsApp:

```bash
curl -X POST http://localhost:8000/briefing/daily \
  -H "Content-Type: application/json" \
  -d '{"send_whatsapp": true}'
```

With Twilio disabled or missing credentials, the response returns a mock send status instead of failing the demo.

Test the inbound WhatsApp webhook locally:

```bash
curl -X POST http://localhost:8000/twilio/whatsapp/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "From=whatsapp:+917045706453" \
  --data-urlencode "Body=What is the top objection?"
```

## Demo Script

1. Open the Streamlit dashboard.
2. Show the developer-style lead dashboard and the bottom-right Ask Co-pilot button.
3. Ask: `What is the top objection today?`
4. Ask: `Which inventory should I push today?`
5. Show the same questions working through WhatsApp from the developer number.
6. Trigger `/briefing/daily` with `send_whatsapp=true` to send the daily WhatsApp brief.
7. Explain that Snowflake can replace mock CSV by switching env vars, while the UI and WhatsApp agent stay the same.

## Tests

```bash
python -m unittest discover -s tests
```

The existing analytics tests remain in place, and the new co-pilot tests cover mock briefing generation, Ask fallback, and action generation.
