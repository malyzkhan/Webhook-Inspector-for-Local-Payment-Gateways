# **[Webhook-Inspector-for-Local-Payment-Gateways](https://github.com/malyzkhan/Webhook-Inspector-for-Local-Payment-Gateways)**

Real-time webhook capture and inspection for local payment gateway integrations. The Phase 1 implementation uses FastAPI, MongoDB Atlas with Motor, Server-Sent Events (SSE), and a Next.js App Router dashboard.

## Architecture

```text
Payment gateway / test client
          |
          v
FastAPI capture API -----> MongoDB webhooks collection
          |                       |
          v                       v
Process-local SSE broker     24-hour TTL retention
          |
          v
Next.js browser inspector <---- history API
```

- **API:** asynchronous FastAPI application in `backend/`.
- **Persistence:** MongoDB Atlas or compatible MongoDB. Motor creates indexes during FastAPI startup.
- **Live delivery:** process-local `asyncio.Queue` subscribers, with SSE heartbeats every 15 seconds.
- **Dashboard:** Next.js App Router application in `frontend/`; loads up to 50 recent events and subscribes to SSE.

## Requirements

- Python 3.10 or later
- Node.js 18.18 or later and npm
- MongoDB Atlas cluster or a reachable MongoDB instance

## Configuration

### Backend

From the repository root in PowerShell:

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

Set these variables in `backend\.env`:

| Variable | Required | Purpose |
|---|---:|---|
| `MONGODB_URI` | Yes | MongoDB connection string. Replace the example placeholders with a database user's credentials. |
| `MONGODB_DATABASE` | No | Database name; defaults to `webhook_saas`. |
| `CORS_ORIGINS` | No | Comma-separated allowed browser origins; defaults to `http://localhost:3000`. |

For Atlas, create a database user with appropriate database access and add your development IP address under Network Access. URL-encode special characters in the connection-string username or password. Keep `.env` files private; never commit credentials or paste them into logs, issues, or chat. The repository ignores `.env`.

### Frontend

```powershell
Copy-Item frontend\.env.example frontend\.env.local
```

`NEXT_PUBLIC_API_URL` sets the API origin used by the browser and defaults to `http://localhost:8000`. Since this value is bundled into the frontend, restart the Next.js development server after changing it.

## Run locally

### Start the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --env-file .env
```

The API listens on `http://localhost:8000`. At startup it verifies the MongoDB connection and ensures the following indexes exist:

- `webhook_ttl`: `created_at` ascending with `expireAfterSeconds=86400`.
- `endpoint_history`: `endpoint_id` ascending and `created_at` descending.

### Start the frontend

In another terminal, from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Select **Create a local endpoint** to generate a random endpoint ID and open `/inspect/<endpoint_id>`.

## API reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/wh/{endpoint_id}` | Capture a request body and query parameters. |
| `GET` | `/api/wh/{endpoint_id}` | Capture query-string callbacks. |
| `GET` | `/api/stream/{endpoint_id}` | Stream new captures as `text/event-stream`; sends a comment heartbeat every 15 seconds. |
| `GET` | `/api/endpoints/{endpoint_id}/history` | Return the newest 50 persisted events for the endpoint. |
| `GET` | `/health` | Return `{"ok": true}` for health monitoring. |
| `GET` | `/docs` | Interactive OpenAPI documentation. |

### Capture and normalization behavior

- Supports `application/json`, `application/*+json`, `application/x-www-form-urlencoded`, `multipart/form-data`, and raw text/bytes.
- Malformed JSON is still captured as text with a parse-error marker instead of being rejected as a validation error.
- Repeated query/form fields are represented as arrays.
- Gateway identification is heuristic: any `pp_` field is tagged `JazzCash`; an `orderId` or `paymentToken` field is tagged `EasyPaisa`; otherwise the event is `Generic`.
- Each document records a generated event ID, endpoint ID, method, request headers, parsed query/body, raw query, Base64-encoded raw body, client IP, gateway tag, UTC timestamp, and capture response status.
- Request body plus query string is limited to 64 KiB. Larger requests receive HTTP 413.
- Successful captures are persisted before they are broadcast to connected SSE clients. MongoDB storage failures return HTTP 503.

### Example requests

Use the endpoint ID shown in the inspector:

```powershell
$endpointId = "YOUR_ENDPOINT_ID"
$webhookUrl = "http://127.0.0.1:8000/api/wh/$endpointId"

Invoke-RestMethod -Method Post -Uri $webhookUrl `
  -ContentType "application/json" `
  -Body '{"pp_ResponseCode":"000","pp_Amount":"10000","pp_TxnRefNo":"TEST-001"}'

Invoke-RestMethod -Method Get `
  -Uri "${webhookUrl}?orderId=TEST-EP-001&transactionStatus=SUCCESS"

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/endpoints/$endpointId/history" |
  ConvertTo-Json -Depth 10
```

The first request is tagged JazzCash and the second EasyPaisa. These are local classification tests, not gateway signature verification or real payment tests.

## Dashboard behavior

- The left panel shows live events and the most recent event history.
- Selecting an event displays headers, query parameters, and parsed payload.
- **Copy URL** copies the endpoint URL; **Copy as cURL** creates a POSIX-shell replay command.
- **Clear List** clears only the browser's current list; it does not delete database records.
- Captured events expire through MongoDB's TTL index. TTL deletion is asynchronous and is not an exact-time deletion guarantee.

## Validation

Frontend type-check and production build:

```powershell
cd frontend
npx tsc --noEmit
npm run build
npm audit
```

Backend syntax compilation:

```powershell
cd backend
python -m compileall -q .
```

Then verify the running API at `/health`, submit the example requests, check that the SSE-connected inspector updates, refresh it to confirm history is loaded, and confirm the corresponding documents in MongoDB Atlas Data Explorer.

## Deployment and operational constraints

- A payment provider cannot reach a developer's `localhost`. Real gateway callbacks require a publicly reachable HTTPS backend URL, for example through a secure development tunnel or deployment.
- Configure `CORS_ORIGINS` with the exact deployed dashboard origin(s); do not use a permissive wildcard for production.
- The capture and history routes currently have no authentication or ownership checks. Treat endpoint IDs as unguessable routing identifiers, not access control. Do not send sensitive production traffic to an untrusted deployment.
- The live-event broker is in process memory. Run one API worker/instance for consistent SSE delivery; multiple workers require a shared broker such as Redis or MongoDB change streams.
- The MongoDB TTL index provides retention cleanup, not a hard storage ceiling. Actual M0 usage depends on event volume, indexes, document sizes, and TTL cleanup delay. Monitor Atlas storage and set appropriate traffic limits before production use.
- Current gateway tags are field-name heuristics. Phase 1 does not validate gateway signatures, guarantee gateway-specific response semantics, replay to localhost, authenticate users, or provide billing.

## Branches

- `main`: shared integration branch.
- `testing`: pre-release testing.
- `prod`: production release line.

Promote reviewed changes from `testing` to `prod` through pull requests after validating the API, frontend, and deployment configuration.
