# Release Notes

## Release 0.3.0

## Status
Validated release-green for the current local release gate.

## Validation Summary
- Backend tests passed: 171 passed
- Backend coverage: 86.41%
- Frontend tests passed: 13 passed across 10 files
- Frontend coverage: 94.02%
- Frontend production build passed
- Widget build passed
- Playwright E2E passed: 4 passed

## Included In This Release
- Multi-tenant authentication and RBAC
- Workspace-scoped document upload, processing, chunking, and indexing
- Hybrid retrieval with reranking and context building
- Streaming chat with citations, feedback, stop-generation, and chat history
- Website ingestion, crawling, cleaning, and indexing
- Lead capture, qualification, and human handoff flows
- Analytics dashboard for chats, leads, performance, and queries
- Notification and delivery infrastructure
- Widget embed system and live widget preview
- Voice input and output feature support
- FAQ management and generation flows
- Export and reporting flows
- Production-oriented scheduling with public booking pages, reminders, and provider adapters
- Security hardening for CSRF, secrets, request tracing, and deployment validation
- Docker Compose, worker, and Nginx deployment baseline

## Notable Release Additions
- Scheduling system with:
  - meeting types
  - availability rules
  - blackout dates
  - booking lifecycle APIs
  - secure reschedule and cancellation links
  - admin scheduling dashboard
  - public booking pages
  - Cal.com provider path
- Structured JSON logging and request ID tracing
- Production secret validation safeguards
- Improved Docker and Compose reliability for local deployment
- Green backend, frontend, widget, and E2E validation gates

## Known Limitations
- Billing and subscriptions are not implemented yet
- CRM integrations are present as framework/scaffolding but not fully productized
- Google Calendar and Outlook Calendar providers are scaffolded but not fully production-complete
- Observability and alerting can be expanded further for enterprise deployments
- Backup, restore, and monitoring automation still depend on deployment environment setup

## Deployment Notes
- Local Docker stack is expected to use:
  - PostgreSQL on host port `5433`
  - Redis on host port `6380`
- Backend local environment should point to those host ports when using the Compose stack from the host machine
- Sensitive local env files remain excluded from Git

## Recommended Next Work
- Implement billing and subscription flows
- Finish CRM integrations
- Complete production OAuth flows for Google Calendar and Outlook Calendar
- Expand monitoring, alerts, and backup automation
