# Advanced Business RAG Chatbot SaaS

Advanced Business RAG Chatbot SaaS is a local-first, multi-tenant business knowledge assistant platform built as a monorepo. It combines document ingestion, website crawling, hybrid retrieval, streaming chat, citations, lead capture, analytics, notifications, and human handoff workflows in a single workspace-isolated system.

The project is currently in a late MVP / early production-foundation stage. Core SaaS, RAG, chat, website ingestion, lead workflows, analytics, notification infrastructure, chatbot customization, and deployment foundations are implemented and locally testable. Billing, CRM integrations, deeper observability, and further deployment hardening are still pending.

## Stack

- Frontend: Next.js 15, React 19, TypeScript, Tailwind CSS
- Backend: FastAPI, SQLAlchemy, Alembic
- Database: PostgreSQL
- Vector store: Qdrant
- LLM and embeddings: OpenAI API
- Local infrastructure: Docker Compose
- Storage: local-first file storage under `storage/`

## Implemented Modules

- Auth and RBAC with JWT, password hashing, protected routes, and workspace access control
- PostgreSQL schema with Alembic migrations
- Document upload and processing for PDF, DOCX, TXT, and CSV
- Document indexing pipeline with chunking, metadata, embeddings, and Qdrant sync
- Advanced retrieval with hybrid search, reranking, and context building
- Streaming chat API with citations, confidence, memory, regenerate, stop-generation, and feedback
- ChatGPT-style chat UI and admin dashboard
- Website URL ingestion, crawling, cleaning, indexing, and dashboard status management
- Lead capture, qualification, human handoff, exports, and admin leads dashboard
- Production-style scheduling with meeting types, workspace availability, blackout dates, secure public booking links, reminders, and calendar-provider adapters
- Workspace analytics for chat, leads, feedback, performance, and query trends
- Notification infrastructure with settings, delivery logs, email/webhook delivery, and queue models
- Customizable chatbot settings for branding, behavior, prompt, lead capture, and analytics preferences

## Pending Modules

- Real billing and subscriptions
- CRM integrations
- Billing and subscriptions
- Fuller embeddable widget surface
- Advanced observability
- Advanced deployment hardening beyond the included production baseline

## Architecture

```text
frontend (Next.js dashboard + chat UI)
        |
        v
backend (FastAPI auth, ingestion, retrieval, chat, website, lead, analytics, notification, settings APIs)
        |
        +--> PostgreSQL (tenants, docs, chats, leads, settings, analytics, notification logs)
        |
        +--> Qdrant (chunk vectors + metadata)
        |
        +--> OpenAI (embeddings + generation)
        |
        +--> storage/uploads (local-first file storage)
```

## Repository Layout

```text
.
|-- backend/
|   |-- alembic/
|   |-- app/
|   |   |-- api/v1/routes/
|   |   |-- core/
|   |   |-- db/
|   |   |-- models/
|   |   |-- schemas/
|   |   `-- services/
|   `-- tests/
|-- frontend/
|   `-- src/
|       |-- app/
|       |-- components/
|       `-- lib/
|-- storage/
|-- nginx/
`-- docker-compose.yml
```

## Core Data Model

Main tables currently represented in the backend models and schema tests:

- `users`
- `workspaces`
- `workspace_members`
- `documents`
- `document_chunks`
- `website_sources`
- `chat_sessions`
- `chat_messages`
- `leads`
- `feedback`
- `analytics_events`
- `unresolved_questions`
- `chatbot_settings`
- `calendar_connections`
- `meeting_types`
- `availability_rules`
- `bookings`
- `booking_attendees`
- `blackout_dates`
- `booking_event_logs`
- `access_logs`

## API Surface

Base URL: `http://localhost:8000/api/v1`

- `/auth`
- `/workspaces`
- `/workspaces/{workspace_id}/documents`
- `/workspaces/{workspace_id}/website-sources`
- `/website*`
- `/workspaces/{workspace_id}/retrieval`
- `/chat`
- `/leads`
- `/analytics`
- `/notifications`
- `/calendar`
- `/meeting-types`
- `/availability`
- `/booking`
- `/settings`
- `/health`

Interactive docs are available at `http://localhost:8000/docs`.

## Scheduling

The platform now includes a production-oriented booking system for chatbot handoff, public scheduling pages, and admin-managed availability.

### Scheduling capabilities

- Detects scheduling intent during lead capture and handoff flows
- Supports provider adapters for Google Calendar, Outlook Calendar, Cal.com, and external booking-link fallback
- Ships with a working Cal.com integration path for live slot lookup and booking sync
- Stores all booking and blackout times in UTC and renders slots in the visitor timezone
- Supports workspace-level and meeting-type-level availability, blackout dates, buffer rules, notice windows, and booking windows
- Includes public booking pages at `/book/{workspace_slug}` plus secure manage links for reschedule and cancellation
- Uses background worker sweeps for reminder delivery

### Scheduling API endpoints

- `GET /calendar/providers`
- `POST /calendar/connect`
- `DELETE /calendar/disconnect`
- `GET /calendar/status`
- `POST /meeting-types/create`
- `GET /meeting-types/list`
- `PUT /meeting-types/{id}`
- `DELETE /meeting-types/{id}`
- `POST /availability/set`
- `GET /availability/get`
- `POST /availability/blackout`
- `DELETE /availability/blackout/{id}`
- `GET /availability/blackout/list`
- `GET /booking/slots`
- `POST /booking/create`
- `POST /booking/reschedule`
- `POST /booking/cancel`
- `GET /booking/list`
- `GET /booking/{id}`
- `GET /booking/manage/{token}`
- `GET /booking/public/{workspace_slug}`

### Admin UI and public pages

- Admin dashboard scheduling console: `http://localhost:3000/dashboard/scheduling`
- Public booking page: `http://localhost:3000/book/{workspace_slug}`
- Secure booking management page: `http://localhost:3000/book/manage/{token}`

### How to use booking links

- Every meeting type exposes a public booking URL from the scheduling dashboard.
- Visitors can book without logging in from `/book/{workspace_slug}`.
- Every confirmed booking returns a secure management URL for self-service reschedule and cancellation.
- Chat-based bookings use the same backend booking engine and create the same management links.

### Calendar setup

1. Run backend migrations so the scheduling tables exist.
2. Open the dashboard scheduling page.
3. Connect a provider from the `Calendar connection` tab.
4. Create one or more meeting types.
5. Configure weekly availability, timezone, blackout dates, and booking limits.
6. Copy a meeting-type booking link or let the chatbot offer scheduling after lead capture or handoff.

### Working provider: Cal.com

The current live provider implementation is Cal.com. Connect it from the dashboard or `POST /calendar/connect` using:

- `provider=calcom`
- `api_key` or `access_token`
- optional metadata such as `base_url`, `calcom_event_type_id`, `calcom_event_type_slug`, `calcom_username`, `calcom_team_slug`, and `calcom_organization_slug`

For meeting types that should sync with Cal.com, set:

- `provider_preference=calcom`
- meeting metadata for the target event type slug or id

When connected, slot lookup can use live Cal.com availability and confirmed bookings store `external_event_id` plus the returned meeting link.

### OAuth configuration

Google Calendar and Outlook Calendar provider modules are scaffolded behind the same adapter system in:

- [calendar_provider_base.py](/d:/Advanced_Business_RAG_Chatbot_SaaS/backend/app/services/calendar_provider_base.py)
- [google_calendar_provider.py](/d:/Advanced_Business_RAG_Chatbot_SaaS/backend/app/services/google_calendar_provider.py)
- [outlook_calendar_provider.py](/d:/Advanced_Business_RAG_Chatbot_SaaS/backend/app/services/outlook_calendar_provider.py)

To enable a production OAuth rollout for Google or Outlook:

1. Create provider credentials in Google Cloud or Microsoft Entra.
2. Register backend redirect URIs for your deployed API domain.
3. Exchange the authorization code server-side and store encrypted refresh/access tokens in `calendar_connections`.
4. Keep tokens backend-only; never expose them to the frontend.
5. Reuse the existing provider adapter methods for busy-slot lookup, event creation, reschedule, and cancellation.

The current repo includes the provider abstraction and persistence model; Cal.com is the ready-to-use path today.

## Local Setup

### Prerequisites

- Node.js 20+
- npm 10+
- Python 3.11+
- Docker Desktop

### 1. Create environment files

```powershell
Copy-Item .env.example .env
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env.local
```

Set at least:

- `OPENAI_API_KEY` in `backend/.env`
- database and Qdrant ports if you want to override defaults
- frontend branding values in `frontend/.env.local` if desired

### 2. Start infrastructure

```powershell
docker compose up -d
```

This starts:

- PostgreSQL on `localhost:5432`
- Qdrant HTTP on `localhost:6333`
- Qdrant gRPC on `localhost:6334`
- Redis on `localhost:6379`

### 3. Start the backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Optional demo seed:

```powershell
cd backend
.venv\Scripts\python -m app.db.seed_demo
```

### 4. Start the frontend

From the repo root:

```powershell
npm install
npm run dev:frontend
```

You can also run it directly from `frontend/` with `npm run dev`.

## Local URLs

- Frontend app: `http://localhost:3000`
- Backend root: `http://localhost:8000`
- Health check: `http://localhost:8000/api/v1/health`
- API docs: `http://localhost:8000/docs`
- Qdrant dashboard/API: `http://localhost:6333/dashboard`

## Recommended Smoke Test

1. Start Docker services.
2. Run backend migrations.
3. Start the FastAPI app and confirm `/api/v1/health` returns `status: ok`.
4. Start the Next.js app and open `http://localhost:3000`.
5. Create an account and log in.
6. Open a workspace, upload a document, and wait for indexing to complete.
7. Add a website source and verify crawl/index status in the dashboard.
8. Open chat, ask a grounded question, and confirm the answer includes citations.
9. Trigger a lead capture or handoff flow and verify it appears in the leads dashboard.
10. Open the scheduling page, create a meeting type, and confirm slots appear on the public booking page.

## Docker And DevOps

### Included deployment files

- [docker-compose.yml](/d:/Advanced_Business_RAG_Chatbot_SaaS/docker-compose.yml)
- [backend/Dockerfile](/d:/Advanced_Business_RAG_Chatbot_SaaS/backend/Dockerfile)
- [frontend/Dockerfile](/d:/Advanced_Business_RAG_Chatbot_SaaS/frontend/Dockerfile)
- [nginx/nginx.conf](/d:/Advanced_Business_RAG_Chatbot_SaaS/nginx/nginx.conf)
- [.github/workflows/deploy.yml](/d:/Advanced_Business_RAG_Chatbot_SaaS/.github/workflows/deploy.yml)

### Docker services

The Compose stack now includes:

- `frontend`: Next.js production server built from a multi-stage image
- `backend`: FastAPI API server with Alembic migrations on startup
- `worker`: dedicated background worker for indexing, exports, notification sweeps, and integration sweeps
- `postgres`: relational database
- `qdrant`: vector database
- `redis`: task queue and cache foundation
- `nginx`: reverse proxy for `/` and `/api/*`

### Docker commands

From the repo root:

```powershell
npm run docker:build
npm run docker:start
npm run docker:logs
npm run docker:restart
npm run docker:stop
npm run docker:migrate
npm run docker:rollback
```

### Docker local run flow

1. Copy environment templates.
2. Set `OPENAI_API_KEY` in `backend/.env`.
3. Start the stack:

```powershell
npm run docker:start
```

4. Open:

- App through Nginx: `http://localhost`
- Frontend directly: `http://localhost:3000`
- Backend directly: `http://localhost:8000`
- Backend readiness: `http://localhost:8000/api/v1/health/ready`

### Multi-environment support

Environment behavior differs by configuration:

- `development`
  - `APP_ENV=development`
  - `WORKER_MODE=inline`
  - frontend usually runs with `npm run dev:frontend`
- `staging`
  - `APP_ENV=staging`
  - `TASK_QUEUE_ENABLED=true`
  - `WORKER_MODE=external`
  - use staging URLs, secrets, and managed services
- `production`
  - `APP_ENV=production`
  - `TASK_QUEUE_ENABLED=true`
  - `WORKER_MODE=external`
  - enable managed Postgres, managed Redis, Qdrant Cloud or private Qdrant, platform TLS, secret managers, and object storage

### Environment variable guide

Root `.env`:

- shared infrastructure ports and connection URLs
- externalized secrets for Compose deployments

`backend/.env`:

- database URL
- OpenAI API key
- JWT secrets
- `INTEGRATION_ENCRYPTION_KEY` for encrypted calendar/provider tokens at rest
- Redis queue settings
- worker mode
- `FRONTEND_URL` so booking and management links point to the correct domain
- storage backend settings and signed URL TTL
- notification and email credentials
- provider credentials such as Cal.com API keys and future Google/Outlook OAuth secrets

`frontend/.env.local`:

- public app name
- API base URL
- site URL
- widget branding values
- make `NEXT_PUBLIC_SITE_URL` match the public host used for booking links

Secrets must not be committed. Use:

- Vercel Environment Variables for frontend secrets
- Render/Railway/AWS secret managers or service-level environment settings for backend secrets
- GitHub Actions secrets for CI/CD deploy hooks and registry credentials

### Scheduling-specific environment variables

At minimum, configure these values before using scheduling outside local demo mode:

- `FRONTEND_URL`
- `JWT_SECRET_KEY`
- `INTEGRATION_ENCRYPTION_KEY`
- `REDIS_URL`
- `TASK_QUEUE_ENABLED=true` for worker-backed reminders in staging or production
- `WORKER_MODE=external` in staging or production
- `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `EMAIL_FROM_ADDRESS` or your SendGrid / SES credentials for confirmations and reminders

## Deployment Guide

### Frontend on Vercel

1. Import the repository into Vercel.
2. Set root directory to `frontend`.
3. Add environment variables from `frontend/.env.example`.
4. Set `NEXT_PUBLIC_API_BASE_URL` to your deployed backend URL.
5. Deploy from `main`.

Recommended production values:

- `NEXT_PUBLIC_SITE_URL=https://app.example.com`
- `NEXT_PUBLIC_API_BASE_URL=https://api.example.com`

### Backend on Render / Railway / AWS

Build source:

- Docker: `backend/Dockerfile`

Start command:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Worker command:

```bash
python -m app.worker
```

Deploy at least two backend services:

- `api`
- `worker`

Use managed persistent services for:

- PostgreSQL: Supabase, Neon, Render Postgres, Railway Postgres, or AWS RDS
- Redis: Upstash, Redis Cloud, Railway Redis, or ElastiCache
- Qdrant: Qdrant Cloud or self-hosted Qdrant
- Storage: AWS S3, Cloudflare R2 using the S3 API, or Supabase Storage

### Database migrations

Automatic production container startup already runs:

```bash
alembic upgrade head
```

Manual migration command:

```powershell
npm run docker:migrate
```

Manual one-step rollback command:

```powershell
npm run docker:rollback
```

Production rollback strategy:

- restore a database backup first if the migration changed data irreversibly
- downgrade only one reviewed revision at a time
- validate the application against the rolled-back schema before reopening traffic

Destructive migration protection:

- production blocks migrations containing obvious destructive operations such as `drop_table`, `drop_column`, or `drop_constraint`
- override only with `ALLOW_DESTRUCTIVE_MIGRATIONS=true` after backup and explicit approval

### Production file storage

Do not use local disk in production.

Supported backends:

- `STORAGE_BACKEND=s3`
- `STORAGE_BACKEND=supabase`

S3 settings:

- `S3_BUCKET_NAME`
- `S3_ENDPOINT_URL` for S3-compatible providers such as R2 or MinIO
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`

Supabase Storage settings:

- `SUPABASE_URL`
- `SUPABASE_BUCKET_NAME`
- `SUPABASE_SERVICE_ROLE_KEY`

Private download behavior:

- S3 objects use presigned URLs
- Supabase objects use signed private URLs
- local development keeps API-mediated local access behavior

### CORS production rules

- development can use local origins such as `http://localhost:3000`
- production must explicitly list allowed origins in `CORS_ALLOWED_ORIGINS`
- wildcard `*` is blocked in production by configuration validation

### Reverse proxy and HTTPS

The included Nginx config routes:

- `/` to the frontend
- `/api/*`, `/docs`, and `/openapi.json` to the backend

For production TLS:

- use platform HTTPS on Vercel/Render/Railway when possible
- if self-hosting, place Nginx behind Let’s Encrypt via Certbot or a cloud load balancer
- redirect HTTP to HTTPS at the platform or load-balancer layer

### Sample URL structure

- Marketing app: `https://www.example.com`
- SaaS app: `https://app.example.com`
- Backend API: `https://api.example.com/api/v1`
- Docs: `https://api.example.com/docs`
- Widget script: `https://app.example.com/widget.js`

## CI/CD

Two workflows are included:

- [tests.yml](/d:/Advanced_Business_RAG_Chatbot_SaaS/.github/workflows/tests.yml)
  - installs dependencies
  - runs backend, frontend, and E2E tests
- [deploy.yml](/d:/Advanced_Business_RAG_Chatbot_SaaS/.github/workflows/deploy.yml)
  - verifies tests
  - builds frontend artifacts
  - builds Docker images
  - tags Docker images with semantic version numbers from [VERSION](/d:/Advanced_Business_RAG_Chatbot_SaaS/VERSION) plus Git SHA
  - optionally pushes images to GHCR
  - optionally triggers Render and Vercel deploy hooks

Required deploy secrets if you want automatic releases:

- `GHCR_USERNAME`
- `GHCR_TOKEN`
- `RENDER_DEPLOY_HOOK_URL`
- `VERCEL_DEPLOY_HOOK_URL`

## Logging, Monitoring, Health, And Scaling

- Backend logging is configured centrally with structured JSON output by default for platform log collection.
- Every request receives an `X-Request-ID` header for trace correlation across logs and support investigations.
- Optional Sentry support can be enabled with `SENTRY_DSN`.
- `/api/v1/health` provides a lightweight liveness endpoint.
- `/api/v1/health/ready` checks database, Qdrant, and Redis readiness.
- Compose health checks are included for frontend, backend, Postgres, Qdrant, Redis, and Nginx.
- The worker now publishes a heartbeat and has its own container health check.
- The backend is stateless for horizontal scaling, with persistence externalized to PostgreSQL, Redis, Qdrant, and storage volumes or cloud storage.
- The worker process handles asynchronous indexing, exports, and queue sweeps separately from the API.

## Backup Strategy

- PostgreSQL: enable daily managed snapshots and point-in-time recovery where available.
- Qdrant: use persistent volumes locally and scheduled snapshot backups in hosted environments.
- Uploaded files and exports: use versioned object storage buckets in production and lifecycle policies for retention.
- Secrets: store only in secret managers, never in the repo.

## Rollback Plan

### Frontend rollback

1. Redeploy the previous Vercel build or previous container image tag from the versioned registry.
2. Repoint traffic only after smoke-checking login and dashboard routes.

### Backend rollback

1. Redeploy the previous backend image tag, for example `rag-backend:0.2.0`.
2. If the release introduced a schema change, run `alembic downgrade -1` only after validating rollback safety.
3. Restart the worker on the matching release version.

### Database restore

1. Restore the most recent verified backup or point-in-time snapshot.
2. Reapply only the migrations that belong to the restored application version.
3. Re-run readiness checks and smoke tests before reopening traffic.

## Cost-Control Notes

- Lowest-cost demo stack:
  - frontend on Vercel hobby
  - backend on Render free or Railway starter
  - Postgres on Supabase free tier or Neon free tier
  - Redis on Upstash free tier
  - Qdrant Cloud starter tier
  - storage on Supabase Storage or Cloudflare R2
- Production upgrade path:
  - move backend to a paid always-on plan
  - use managed Postgres with backups
  - separate worker from API with independent scaling
  - shift uploads and exports to S3-compatible object storage
  - tune OpenAI and Qdrant usage by workspace and retention policies
- Cost minimization tips:
  - keep `RETRIEVAL_FINAL_TOP_K` tight
  - apply lifecycle rules to old exports
  - store snapshots privately and compress long-lived artifacts
  - scale worker independently from API traffic

## Post-Deployment Smoke Test

After each deployment, verify:

1. Login succeeds for a real user account.
2. Document upload completes and indexing moves from `pending` to `indexed`.
3. Website ingestion completes and source status becomes `indexed`.
4. RAG chat returns a grounded answer.
5. Citations are visible in the response.
6. Lead capture creates a lead record.
7. Widget embed loads from the public script URL.
8. Analytics pages load without API errors.
9. Export generation completes and the download link works.

Recommended smoke order:

```text
frontend root -> backend /health -> backend /health/ready -> login -> upload -> website source -> chat -> citations -> lead -> analytics -> export -> widget
```

## Troubleshooting

- If the backend fails readiness, check `DATABASE_URL`, `QDRANT_URL`, and `REDIS_URL`.
- If documents stay `pending`, verify the `worker` service is running and that Redis is healthy.
- If the frontend loads but API calls fail, confirm `NEXT_PUBLIC_API_BASE_URL` points to the deployed backend origin.
- If HTTPS redirects loop, verify your proxy or platform is forwarding `X-Forwarded-Proto`.
- If uploads fail in containers, confirm the `storage_uploads` volume is mounted and writable.
- If production boot fails immediately, check that `STORAGE_BACKEND` is not `local`.
- If presigned downloads fail, verify storage credentials, bucket permissions, and signed URL TTL.
- If migrations are blocked in production, review the migration file for destructive operations and take a backup before overriding the guard.
- If deploy hooks do nothing, verify the GitHub Actions secrets are populated and enabled for the repository.

## Testing

The project now uses a four-layer QA strategy:

- Unit tests for authentication, RBAC, document processing, embeddings, retrieval, leads, notifications, and integrations
- Integration tests for the RAG pipeline, chunking, hybrid retrieval, reranking, and graceful fallback paths
- API tests for auth, chat, documents, leads, and analytics endpoints including permissions and error handling
- Frontend component and end-to-end tests for chat rendering, streaming UX, citations, lead capture, and analytics flows

### Test layout

```text
backend/tests/
|-- api/
|-- contracts/
|-- fixtures/
|-- integration/
|-- load/
|-- migrations/
|-- performance/
|-- security/
`-- unit/

frontend/tests/
|-- component/
|   `-- __snapshots__/
`-- setup.ts

e2e/tests/
|-- accessibility.spec.ts
`-- full-flow.spec.ts
```

### Install test dependencies

Backend:

```powershell
cd backend
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

Frontend and E2E:

```powershell
cd ..
npm install
npx playwright install
```

### Run all tests

From the repo root:

```powershell
npm run test
```

### Run backend tests only

```powershell
npm run test:backend
```

### Run scheduling tests only

```powershell
cd backend
.venv\Scripts\python -m pytest --no-cov backend\tests\unit\scheduling\test_slot_generator.py backend\tests\api\test_scheduling_api.py -q
```

### Run frontend component tests only

```powershell
npm run test:frontend -- --run
```

### Run end-to-end tests only

```powershell
npm run test:e2e
```

### Run cross-browser E2E tests

```powershell
npm run test:e2e:cross-browser
```

This runs the production-like Playwright flow against:

- Chrome
- Firefox
- Mobile Chrome
- Edge on Windows hosts where `msedge.exe` is available
- Mobile Edge on Windows hosts where `msedge.exe` is available

### Re-run only failed tests

```powershell
npm run test:failed
```

### Watch mode for frontend development

```powershell
npm run test:watch
```

### Pre-deployment verification

```powershell
npm run test:predeploy
```

### Coverage

- Backend coverage is generated through `pytest-cov`, emits terminal missing-lines output plus `backend/coverage.xml` and `backend/coverage_html/`, and fails if total coverage drops below `85%`.
- Frontend coverage is generated through Vitest, emits terminal output plus `frontend/coverage/`, and fails if critical UI coverage drops below `80%` for statements and lines.
- Coverage enforcement focuses on critical late-MVP flows: auth, workspace isolation, ingestion, retrieval, chat, leads, analytics, notifications, dashboard, and integrations.

### What is covered

- RAG pipeline: sample TXT/PDF extraction, chunking correctness, embedding batching and failure handling, vector indexing, hybrid search, reranking, and offline-safe retrieval fallbacks
- Security: unauthorized access, cross-workspace blocking, invalid upload rejection, prompt-injection sanitization, rate limiting, and bearer-token misuse
- API reliability: success responses, validation failures, and safe 500 responses
- Contract testing: JSON schema validation for auth, chat, document, lead, and analytics request/response structures
- Chaos and resilience: transient DB/vector/LLM failure simulation with safe fallback behavior instead of silent crashes
- Data integrity: duplicate chunk prevention, metadata mapping, and workspace-isolated records
- Resilience: embedding, vector, and timeout retry handling plus fallback behavior
- Streaming: chunk ordering, termination events, and stop-generation behavior
- Load/performance: concurrent chat requests, multiple uploads, and latency guardrails for key API paths
- Migration safety: Alembic upgrade-path smoke tests for schema compatibility
- Observability: request logging, prompt-injection audit events, captured error logs, and slow-request latency assertions
- Feature flags and privacy: lead/voice toggle coverage, legacy-record compatibility, workspace-isolated exports, and hard-delete validation
- Upload and abuse edge cases: large files, corrupt files, empty uploads, rapid API bursts, and spam chat attempts
- Frontend behavior: loading states, chat rendering, streaming updates, citation display, keyboard flows, and snapshot coverage for key UI components
- Accessibility: keyboard-first navigation, labels, and baseline ARIA-friendly interaction checks
- End-to-end flow: signup, document upload, chat, lead capture, analytics navigation, and widget preview smoke coverage using Playwright with mocked backend responses and console-error assertions
- Deployment baseline: Dockerized frontend/backend services, Redis-backed worker flow, reverse proxy routing, readiness checks, and CI build automation

### Scheduling test focus

The scheduling suites cover:

- availability calculation
- timezone-aware slot rendering
- booking creation
- double-booking prevention
- secure token-based cancellation and rescheduling
- provider-sync behavior through mocked calendar calls
- workspace isolation for booking data

### Known limitations

- Browser suites require installing additional npm packages and Playwright browsers before first run.
- The Playwright flow currently mocks backend APIs so it can run offline and deterministically in CI.
- Edge-specific E2E coverage runs on Windows hosts with a local Edge installation; CI uses Chromium, Firefox, and mobile Chromium for portability.
- Snapshot tests are intentionally scoped to critical UI surfaces to keep review noise manageable.
- Existing legacy `unittest` backend tests remain in place and continue to complement the new pytest-based structure.

### Pre-deployment checklist

- `npm run test:ci` passes cleanly
- `npm run test:predeploy` confirms required environment files and coverage artifacts exist
- No browser console errors appear in E2E verification
- Backend coverage remains at or above `85%`
- Frontend critical UI coverage remains at or above `80%`
- Auth, chat, documents, leads, analytics, RAG, security, and resilience suites are green

## Notes

- Uploaded files are stored locally only for development; production should use S3 or Supabase Storage.
- Background indexing is now dispatched through a Redis-backed worker path when `TASK_QUEUE_ENABLED=true`, with inline fallback for local development.
- Notification and integration deliveries remain DB-backed and are swept by the dedicated worker process.
- The repo is organized as a monorepo, but only the frontend is currently wired into the root npm workspace.
