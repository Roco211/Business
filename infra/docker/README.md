# Infra Docker

This directory defines the local infrastructure for the current MVP foundation:

- MySQL
- Redis
- MinIO
- API service
- Worker service

Phase 2 adds SQLAlchemy and Alembic-backed persistence. The backend now expects a migration-managed schema for DB-backed routes such as mock login bootstrap and session bootstrap. By default the application derives its database URL from `MYSQL_*` variables, and `DATABASE_URL` is only needed when you want to override that behavior explicitly.

The compose stack now includes a `migrator` service so the API and worker start behind an explicit schema upgrade step.
