# PakHook

PakHook is a Phase 1 webhook inspector for local payment gateway integrations. It accepts JSON, URL-encoded forms, multipart forms, raw text, and GET query-string callbacks; stores captures in MongoDB with a 24-hour TTL; and streams new events to a Next.js inspector over SSE.

## Requirements

- Python 3.10+
- Node.js 18.18+ and npm
- MongoDB Atlas M0 or a local MongoDB instance

## Configure and run the API

```powershell
cd backend
Copy-Item .env.example .env
```

Set `MONGODB_URI` in `backend/.env`, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --env-file .env
```

The API listens on `http://localhost:8000`. Its startup hook creates the 24-hour TTL index and the endpoint/history compound index before serving requests.

## Configure and run the dashboard

In another terminal:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000/inspect/<endpoint-id>`. Generate an unguessable endpoint ID, for example with `python -c "import uuid; print(uuid.uuid4())"`, and register the displayed webhook URL with the gateway. For local testing, expose port 8000 through an HTTPS tunnel and use the tunnel URL as `NEXT_PUBLIC_API_URL`.

The frontend loads the last 50 stored events and then subscribes to the endpoint's SSE stream. "Clear List" clears the current browser view only; it does not delete retained events from MongoDB. Captures expire automatically after 24 hours.

## API

- `POST /api/wh/{endpoint_id}` — capture a webhook in any supported body format.
- `GET /api/wh/{endpoint_id}?key=value` — capture GET callbacks.
- `GET /api/stream/{endpoint_id}` — subscribe to live events.
- `GET /api/endpoints/{endpoint_id}/history` — return up to 50 recent events.
- `GET /health` — health check.

Request bodies and query strings larger than 64 KiB combined are rejected with HTTP 413. "Copy as cURL" preserves the captured raw request body and query string; body-bearing commands use `base64 --decode` in a POSIX-compatible shell. The capture endpoint is intentionally unauthenticated for webhook compatibility; use a high-entropy endpoint ID and do not treat it as an authorization boundary. Configure `CORS_ORIGINS` to the exact dashboard origins before deployment. The in-memory SSE broker is process-local, so run a single API worker unless a shared broker is added.
