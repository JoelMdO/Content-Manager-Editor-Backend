# Backend Test Implementation

## Scope

This document describes how to validate `Backend-Editor` at three levels:

1. Fast local unit and API tests using the SQLite test configuration.
2. Container integration tests using Django and PostgreSQL.
3. Manual or Jest requests against a running backend container.

The test suite lives in `Backend-Editor/src/*/tests/` and in the backend integration test locations under `Backend-Editor/tests/` when present.

## Prerequisites

- Python and the project environment installed from `Backend-Editor/pyproject.toml`
- Docker Desktop for container tests
- Node.js 18+ and `npx` for the standalone Jest check
- Postman for manual request checks
- Test values for `PROXY_KEY` and, when applicable, `RAG_INTERNAL_TOKEN`

Never use production credentials or a persistent development database for disposable write tests.

## Local unit and API tests

From `Backend-Editor`:

```bash
PROXY_KEY=test-proxy-key RAG_INTERNAL_TOKEN=test-rag-token pytest -q
```

Using Django's test runner:

```bash
cd src
DJANGO_SETTINGS_MODULE=config.test_settings PROXY_KEY=test-proxy-key python manage.py test
```

The test settings use the local SQLite database, so these commands do not require Docker, PostgreSQL, or Redis. The backend Makefile provides the same isolated workflow:

```bash
cd Backend-Editor
make test
```

To start the local development server with the test database:

```bash
cd Backend-Editor
make serve
```

The server is normally available at `http://127.0.0.1:8002`.

## What unit tests should cover

Article tests should verify:

- valid article creation and updates
- required and read-only fields
- valid status values
- CMS block JSON stored in `body`
- image primary-key associations
- article retrieval and draft listing

Authentication tests should verify:

- successful and rejected login
- user upsert behavior for new and existing users
- proxy-key protection for internal endpoints
- password-reset response behavior without email enumeration
- logout and token refresh behavior when enabled

Health tests should verify service status and database connectivity responses. Tests for the RAG corpus route should only be enabled when the route is mounted; the current implementation leaves that route inactive.

## Container integration tests

Start the CMS integration services from the repository root:

```bash
docker compose -f Backend-Editor/docker-compose.ci-integration.yml up -d --build
```

Wait for the health endpoint and inspect the services:

```bash
until curl -fsS http://localhost:8080/up/ >/dev/null; do sleep 2; done
docker compose -f Backend-Editor/docker-compose.ci-integration.yml ps
docker compose -f Backend-Editor/docker-compose.ci-integration.yml logs web
docker compose -f Backend-Editor/docker-compose.ci-integration.yml logs db
```

Run the integration marker when the repository provides integration tests:

```bash
pytest Backend-Editor/tests/integration/ -m cms_integration -q
```

If the test configuration is already running from `Backend-Editor`, use its local test command instead of supplying the workspace-relative path.

Clean up after the run:

```bash
docker compose -f Backend-Editor/docker-compose.ci-integration.yml down
```

Use `down --volumes` only when the database contents should be deleted.

## Standalone HTTP validation

The standalone flow exercises the real Django container and PostgreSQL database without starting the editor frontend, translation API, proxy, Redis, or the root Compose stack.

Health check:

```bash
curl -fsS http://localhost:8080/up/
curl -fsS http://localhost:8080/
```

List drafts:

```bash
curl -fsS http://localhost:8080/articles/
```

Create a disposable draft:

```bash
curl -fsS -X POST http://localhost:8080/articles/ \
  -H 'Content-Type: application/json' \
  -d '{
    "article_id": "standalone-http-test",
    "title": "Standalone HTTP test",
    "status": "draft",
    "body": [{"type": "paragraph", "content": "Disposable integration data."}]
  }'
```

Expected results are HTTP 200 for health and listing requests and HTTP 201 for a successful article creation. The current article API does not expose a delete endpoint, so remove the database volume after a disposable run if necessary.

## Jest request check

When `backend-editor.standalone.test.js` is available at the repository root, run:

```bash
npx --yes jest --runInBand backend-editor.standalone.test.js
```

For a different backend address:

```bash
API_BASE_URL=http://localhost:8080 npx --yes jest --runInBand backend-editor.standalone.test.js
```

This check should use real `fetch` requests and cover `/up/`, `/`, and `/articles/`, including a uniquely titled draft write.

## Postman checks

Against `http://localhost:8080` verify:

- `GET /up/` returns 200.
- `GET /articles/` returns 200 and a JSON array.
- `POST /articles/` with a valid CMS block list returns 201.
- Protected internal requests include `x-internal-proxy-key` matching `PROXY_KEY`.
- Auth requests use the documented JSON payloads and expected status codes.

Keep request bodies disposable and inspect container logs when a response is 500 or the health endpoint returns 503.

## Troubleshooting

- `503` from `/up/databases`: PostgreSQL is not ready or the database settings are wrong; inspect the `db` health state and logs.
- `400` from article creation: confirm `body` is a JSON list and `status` is `draft`, `published`, or `archived`.
- `401` or `403` on internal routes: check the exact proxy header name and configured test value.
- Startup `500`: verify `Backend-Editor/.env` exists and that Compose overrides match the service configuration.
- Port conflict: change the host mapping, then set `API_BASE_URL` to the new port.
- Missing RAG endpoint: this is expected while `RagCorpusView` remains commented out and unmounted.
