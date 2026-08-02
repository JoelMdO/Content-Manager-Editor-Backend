# Backend Editor Documentation

## Overview

`Backend-Editor` is a Django REST backend for the Content Manager editor. It stores article drafts and published content, manages article images, provides authentication endpoints, and exposes health checks.

The backend is separate from:

- `Editor/`: the Next.js editor frontend.
- `AI-Translation-API/`: the FastAPI translation and RAG service.
- `Proxy/`: the reverse proxy used by the workspace stack.

## Technology and structure

- Python, Django, and Django REST Framework
- PostgreSQL in runtime containers
- SQLite in the local test configuration
- Redis and Celery for cache and background-work infrastructure
- Gunicorn, Docker, and Docker Compose
- SimpleJWT when the dependency is installed outside tests

Important paths:

- `src/manage.py`: Django management entry point
- `src/config/`: project settings, URLs, WSGI, and Gunicorn configuration
- `src/articles/`: article and image models, serializers, views, and routes
- `src/users/`: authentication and user-management endpoints
- `src/up/`: health-check endpoints
- `compose.yaml`: local service orchestration
- `pyproject.toml`: Python dependencies and tooling

## Data model

### ArticleModel

- `id`: UUID primary key
- `article_id`: optional frontend or external article identifier
- `title`: article title
- `status`: `draft`, `published`, or `archived`
- `body`: JSON list containing CMS/editor blocks
- `images`: many-to-many relation to `ArticleImageModel`
- `created_at`, `updated_at`, and optional `published_at`

Published articles may be scheduled for optional replication to the Neon database. The replication helper copies article metadata and `body`; image files are not replicated.

### ArticleImageModel

Stores image metadata and optional local files. Relevant fields include `type`, `image_id`, `file_name`, `file`, and `cloudinary_url`. The model includes a helper for creating an image from base64 data.

## Routes and API

Top-level routes are defined in `src/config/urls.py`:

| Route | Purpose |
| --- | --- |
| `/` | Service status and Django version |
| `/up/` | Basic health check |
| `/up/databases` | Database connectivity check |
| `/articles/` | Article API |
| `/auth/` | Authentication and user API |
| `/admin/` | Django admin |

### Articles

`POST /articles/` creates or updates an article. The JSON payload may contain `article_id`, `title`, `status`, `body`, and an `images` array of image primary keys. Server-managed fields such as IDs and timestamps are read-only.

`GET /articles/` lists draft articles. `GET /articles/<title>` retrieves an article by title.

The editor commonly uploads images to Cloudinary and stores the resulting URLs in the article body before saving the article. Although image serializers and model helpers exist, a dedicated `POST /articles/images/` route is not currently active.

### Authentication

Routes under `/auth/` include:

- `POST /auth/login/`: authenticate with email and password
- `POST /auth/token/refresh/`: refresh a SimpleJWT token when enabled
- `POST /auth/users/`: internally upsert a Django user
- `POST /auth/password-reset/`: start Django's password-reset flow
- `POST /auth/logout/`: clear the Django session

The NextAuth integration uses JWT-only sessions. The frontend authenticates credentials through Django and upserts the user after OAuth or credentials sign-in; it does not use a NextAuth database adapter.

### Health

- `GET /`: minimal JSON service response
- `GET /up/`: returns HTTP 200 when the service is running
- `GET /up/databases`: checks database connectivity and returns an error status when unavailable

### RAG corpus status

Older documentation described `GET /articles/rag-corpus/?lang=en|es`. In the current backend, `RagCorpusView` is commented out and the route is not mounted. Treat this endpoint as inactive until the view and URL are restored.

## Security and configuration

Important environment variables include:

- `DJANGO_SECRET_KEY` or `SECRET_KEY`
- `DEBUG` and `ALLOWED_HOSTS`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT`
- `REDIS_URL`
- `PROXY_KEY` for internal proxy-protected operations
- `RAG_INTERNAL_TOKEN` if RAG ingestion is enabled
- `NEON_URL` for optional Neon replication
- SMTP variables for password-reset email delivery

The runtime database is PostgreSQL. `src/config/test_settings.py` switches tests to the local SQLite database. Redis-backed services fall back to Django's local-memory cache when Redis is unavailable in tests.

Internal endpoints must validate the configured proxy key. Do not commit real secrets from `.env` files.

## Docker runtime

The backend Compose configuration provides PostgreSQL and Django services, with optional Redis, Celery worker, JavaScript, and CSS services depending on the selected profile. The application is served by Gunicorn from `/app/src`.

The root workspace proxy may expose the articles API under `/api/articles`, but the CMS backend is not automatically part of the root Compose stack. When running it separately, ensure the proxy target and host port match the backend service.

## Authentication migration record

Firebase authentication was replaced by Django authentication with NextAuth JWT-only sessions:

- Google OAuth remains in the frontend.
- Credentials sign-in calls Django's login endpoint.
- The sign-in callback upserts the user in Django.
- Firebase adapters, Firebase admin persistence, and Firebase password-reset calls are removed.
- Django handles password-reset email delivery for email/password users.
- Google account recovery remains managed by Google.

When changing this flow, keep the backend contract and the frontend callback in sync, and protect internal user-upsert calls with the configured proxy key.

## Source of truth

For behavior that differs from this document, use the implementation in `src/config/urls.py`, `src/articles/`, `src/users/`, and `src/config/settings.py` as the source of truth.
