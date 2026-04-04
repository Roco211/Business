# Infra Docker

This directory defines the local infrastructure for the current MVP foundation:

- MySQL
- Redis
- MinIO
- API service
- Worker service

Phase 2 adds SQLAlchemy and Alembic-backed persistence. The backend now expects a migration-managed schema for DB-backed routes such as mock login bootstrap and session bootstrap. By default the application derives its database URL from `MYSQL_*` variables, and `DATABASE_URL` is only needed when you want to override that behavior explicitly.

Phase 3A extends that persistence layer with the message and task ledger foundation. The local stack still brings up MySQL, Redis, MinIO, API, and worker services, but this phase only exercises the DB-backed intake path and does not yet introduce runtime consumers, confirmations, or WebSocket session events.

The compose stack now includes a `migrator` service so the API and worker start behind an explicit schema upgrade step.

Phase 4A adds a dry-run runtime worker on top of that ledger. Fresh message intake now produces pollable task runs, the worker can consume them asynchronously, and runtime outcomes are written back into the session as read-only system messages. This phase still avoids confirmation flows, inventory mutation, audit trails, and WebSocket push.
