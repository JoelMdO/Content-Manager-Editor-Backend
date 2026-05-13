# Backend Editor — Local Run (Backend-Editor only)

This file documents how to run the Backend-Editor (Content Manager) locally for development and tests.

## Quick start (development with Docker)

1. From the workspace root, build and run the CMS CI/dev compose for local integration:

```bash
docker compose -f docker-compose.cms-ci.yml up -d --build
```

2. Wait for the `cms` (web) service to become healthy. Check:

```bash
docker compose -f docker-compose.cms-ci.yml ps
docker compose -f docker-compose.cms-ci.yml logs web -f
```

3. The CMS container exposes the app at `http://localhost:8080` by default (the compose maps container port 8000 to host 8080).

## Running unit tests (Django test runner / pytest)

Unit tests live under `src/*/tests/` and can be run either with Django's test runner or `pytest` depending on preference.

Run via `manage.py` (Django test runner):

```bash
cd "Backend-Editor/src"
DJANGO_SETTINGS_MODULE=config.test_settings PROXY_KEY=test-proxy-key python manage.py test
```

Run via `pytest` (recommended for local development):

```bash
cd "Backend-Editor"
PROXY_KEY=test-proxy-key RAG_INTERNAL_TOKEN=test-rag-token pytest -q
```

## Integration tests (live-container)

Prerequisites: Docker Desktop running; no other services on ports `8080` and `5432`.

Start the integration compose and run the pytest marker for integration:

```bash
docker compose -f docker-compose.ci-integration.yml up -d --build
pytest tests/integration/ -m cms_integration -q
docker compose -f docker-compose.ci-integration.yml down --volumes
```

## Environment variables

- `PROXY_KEY` — internal-proxy-key used in tests (default for test runs: `test-proxy-key`).
- `RAG_INTERNAL_TOKEN` — used by RAG corpus tests (default in tests: `test-rag-token`).
- `CMS_BASE_URL`, `CMS_RAG_TOKEN`, `CMS_PROXY_KEY` — used by integration tests when targeting an externally-run CMS instance.

## Notes

- Unit tests that use `TestCase` or `APITestCase` still run against a test DB created by Django. They are fast to run locally without Docker.
- Integration tests exercise a running container and a real Postgres DB. Use them for CI or end-to-end validation.
