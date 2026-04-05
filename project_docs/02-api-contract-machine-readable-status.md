# 02. API Contract Machine-Readable Status

Date: `2026-04-05`

The repository now includes a machine-readable OpenAPI contract snapshot generated from the real FastAPI application.

## Source Of Truth

- Narrative explanation remains in [02-api-contract.md](/C:/Users/roco2/Downloads/Business/.worktrees/phase11b-openapi-contract-v0.1/project_docs/02-api-contract.md)
- Machine-readable contract snapshot lives at:
  - `project_docs/generated/openapi-v1.json`

## Generation Rule

- The snapshot is generated from `app.main:create_app`
- It is not hand-authored
- Intentional API contract changes should update both:
  - the real FastAPI routes/contracts
  - the committed OpenAPI snapshot

## Regeneration

Run:

```bash
python backend/scripts/generate_openapi_snapshot.py
```

Then re-run the backend test suite so snapshot drift is validated before commit.
