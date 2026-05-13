# Backend Editor — General Overview

This document consolidates endpoint reference, integration notes, and high-level architecture for the Backend-Editor (Content Manager) service.

## Summary

- Purpose: provide persistent storage and HTTP APIs for authoring articles (drafts, images, published content) and an internal RAG corpus endpoint used by other services.
- Stack: Python / Django, Django REST Framework, PostgreSQL, Gunicorn. Tests use `pytest` + Django test runner.

## Public API Endpoints

- `POST /articles/` — create/update article draft. Accepts JSON body with `body` (CMS blocks), optional `title`, `article_id`, `status` (draft|published|archived), and optional `images` array of image PKs. Responds with serialized article including `id`, `created_at`, `updated_at`.
- `POST /articles/images/` — image upload (multipart or JSON base64). Protected by `X-Internal-Proxy-Key` header matching `PROXY_KEY` env var. Returns created image metadata (`id`, `image_id`, `file_name`, optional `cloudinary_url`).
- `GET /articles/rag-corpus/?lang=en|es` — returns published articles as simple objects `{id, title, plain_text, language}` for RAG ingestion. Requires `X-RAG-Token` header matching `RAG_INTERNAL_TOKEN`.
- Auth endpoints under `/auth/` — login, upsert user, password reset, logout. Login returns JWT `access` and `refresh` tokens.
- Health endpoints: `GET /` (home), `GET /up/`, `GET /up/databases`.

## Security & Secrets

- `PROXY_KEY`: required for internal endpoints such as image uploads and user upsert when called via internal proxies.
- `RAG_INTERNAL_TOKEN`: required to call the RAG corpus endpoint.
- JWT: authentication uses signed access & refresh tokens (access ~12h, refresh ~7d); refresh endpoint available at `/auth/token/refresh/`.

## Integration with other apps and APIs

- Editor frontend: typically uploads images to Cloudinary and then posts article payloads to `/articles/`. The Editor may also call a notification API (configured via `URL_API_*` env vars) once it has saved/published an article.
- Proxy (nginx template): the workspace includes a proxy template that forwards `/api/articles` to the CMS service and enforces `x-internal-proxy-key` checks.
- RAG ingestion: a separate ingestion service (FastAPI) calls `/articles/rag-corpus/` with `X-RAG-Token` to fetch plain-text corpus for vectorization.

## Docker / Compose notes

- Compose files: the repo includes `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.ci.yml`, and a specialized `docker-compose.cms-ci.yml` for CMS integration runs.
- CI integration: `docker-compose.cms-ci.yml` and `docker-compose.ci-integration.yml` are used by CI to start the CMS + Postgres for integration tests.

## Recommended Actions

- If you want the CMS available via the workspace proxy, add a `cms` service to the root `docker-compose.yml` and update `Proxy/ngnix.config.template` to proxy `/api/articles` to that service name.
- If the Editor should stop uploading images to Cloudinary and instead rely on the CMS, implement the `POST /articles/images/` upload view to accept multipart/base64 and store `ArticleImageModel` records.

## Where to find code

- Django project entry: `src/manage.py`
- URL config: `src/config/urls.py`
- Articles app: `src/articles` (models, serializers, views)
- Users app: `src/users` (auth endpoints)

If you want edits to expand any section (endpoints, example payloads, or to add the recommended `cms` compose service), tell me and I will update the overview.
