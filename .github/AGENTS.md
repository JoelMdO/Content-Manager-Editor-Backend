# AGENTS.md — Django CMS Backend

## Overview

Django 6 REST API that serves as the content management backend for the Blog Editor.
It stores articles and images in PostgreSQL, exposes a DRF REST API consumed by the
Next.js editor, and provides an internal endpoint for the FastAPI RAG ingestion service.
Background tasks run via Celery + Redis. Static files are served with WhiteNoise.

---

## Tech Stack

| Concern            | Library / Tool                         |
| ------------------ | -------------------------------------- |
| Framework          | Django 6.0                             |
| Language           | Python 3.13+                           |
| API layer          | Django REST Framework 3.15             |
| WSGI server        | gunicorn                               |
| Database           | PostgreSQL 16 (psycopg 3)              |
| Cache / broker     | Redis                                  |
| Task queue         | Celery 5                               |
| Static files       | WhiteNoise                             |
| CORS               | django-cors-headers                    |
| Image handling     | Pillow                                 |
| Environment config | python-dotenv                          |
| Linting            | ruff (line-length 79)                  |
| Package manager    | uv (via pyproject.toml)                |
| Container runtime  | Docker + docker-compose (compose.yaml) |

---

## Directory Layout

```
src/
├── manage.py
├── config/
│   ├── settings.py   # All Django settings; env-driven
│   ├── urls.py       # Root URL conf
│   └── wsgi.py
├── articles/         # Core CMS Django app
│   ├── models.py     # ArticleModel + ArticleImageModel
│   ├── serializers.py
│   ├── views.py      # ArticleDraftViewSet + RagCorpusView
│   ├── urls.py
│   ├── admin.py
│   └── tests.py
├── pages/
│   ├── views.py      # Home page
│   └── urls.py
├── up/
│   ├── views.py      # Health-check endpoints
│   └── urls.py
└── templates/
```

---

## URL Routes

| Path                        | View                  | Description                                    |
| --------------------------- | --------------------- | ---------------------------------------------- |
| `GET /up/`                  | `up.views.index`      | Liveness probe (200)                           |
| `GET /up/databases`         | `up.views.databases`  | Readiness probe (PostgreSQL + Redis checks)    |
| `GET /`                     | `pages.views.home`    | Home page template                             |
| `POST /articles/`           | `ArticleDraftViewSet` | Create a new article draft                     |
| `GET /articles/rag-corpus/` | `RagCorpusView`       | Internal: published articles for RAG ingestion |
| `/admin/`                   | Django admin          | Admin interface                                |

---

## Data Models

### ArticleModel

| Field          | Type            | Notes                                |
| -------------- | --------------- | ------------------------------------ |
| `id`           | UUIDField (PK)  | Auto-generated                       |
| `article_id`   | CharField       | Slug from the frontend `id` block    |
| `title`        | TextField       |                                      |
| `status`       | CharField       | `draft` / `published` / `archived`   |
| `body`         | JSONField       | List of block dicts from the editor  |
| `images`       | ManyToManyField | Linked `ArticleImageModel` instances |
| `created_at`   | DateTimeField   | Auto                                 |
| `updated_at`   | DateTimeField   | Auto                                 |
| `published_at` | DateTimeField   | Nullable                             |

### ArticleImageModel

| Field            | Type       | Notes                                 |
| ---------------- | ---------- | ------------------------------------- |
| `id`             | UUIDField  | Auto-generated                        |
| `type`           | CharField  | Unique; matches `imageId` on frontend |
| `image_id`       | CharField  | Unique identifier                     |
| `file_name`      | CharField  |                                       |
| `file`           | ImageField | Stored under `article_images/`        |
| `cloudinary_url` | URLField   | Optional CDN URL                      |

---

## Authentication

- `POST /articles/` — no DRF token auth on the route itself; relies on Django CSRF
  middleware when called from the browser-based editor.
- `GET /articles/rag-corpus/` — protected by `X-RAG-Token` header. The server checks the
  value against `RAG_INTERNAL_TOKEN` using `hmac.compare_digest`. Must NOT be exposed via
  the public proxy.
- `/admin/` — Django admin session auth.

---

## Configuration (Environment Variables)

| Variable             | Required | Description                                                          |
| -------------------- | -------- | -------------------------------------------------------------------- |
| `SECRET_KEY`         | Yes      | Django secret key                                                    |
| `DEBUG`              | No       | `true` / `false` (default: `false`)                                  |
| `ALLOWED_HOSTS`      | No       | Comma-separated hosts                                                |
| `POSTGRES_DB`        | Yes      | PostgreSQL database name                                             |
| `POSTGRES_USER`      | Yes      | PostgreSQL username                                                  |
| `POSTGRES_PASSWORD`  | Yes      | PostgreSQL password                                                  |
| `POSTGRES_HOST`      | No       | Default: `postgres`                                                  |
| `POSTGRES_PORT`      | No       | Default: `5432`                                                      |
| `REDIS_URL`          | No       | Default: `redis://redis:6379/0`                                      |
| `RAG_INTERNAL_TOKEN` | Yes\*    | Shared secret for `/articles/rag-corpus/` (\*required in production) |

Never commit `.env` files. All secrets must come from environment variables.

---

## Adding a New Django App

1. `python manage.py startapp <name>`
2. Add to `INSTALLED_APPS` in `config/settings.py`.
3. Define models in `<name>/models.py` and run `python manage.py makemigrations`.
4. Define DRF serializers in `<name>/serializers.py`.
5. Define views in `<name>/views.py` (use `APIView` or `ModelViewSet`).
6. Register URLs in `<name>/urls.py` and include in `config/urls.py`.
7. Register models in `<name>/admin.py` with `list_display` and `search_fields`.
8. Add tests in `<name>/tests.py` (see `.github/skills/test.md`).

## Adding a New API Endpoint

1. Add a view in the relevant app's `views.py` (extend `APIView` or add a route to an
   existing `ViewSet`).
2. Register the URL in `<name>/urls.py`.
3. If the endpoint is internal-only (e.g. RAG), protect it with `hmac.compare_digest`
   and document in the docstring that it must NOT be exposed via the public proxy.

---

## Development

```bash
# Start all services (Django, PostgreSQL, Redis)
make up

# Run migrations
make migrate

# Create superuser
make superuser

# Open Django shell
make shell-django

# Open psql shell
make shell-db

# Rebuild all images
make build

# Tail logs
make logs
```

Or run the Django dev server directly (requires local PostgreSQL + Redis):

```bash
cd src
python manage.py migrate
python manage.py runserver 8002
```

---

## Testing

Use `pytest-django` + `model-bakery` for fast, isolated tests. Use Django's test client
for view/endpoint tests. Never hit a real database in unit tests — use the
`@pytest.mark.django_db` marker only for integration tests.

```bash
pip install pytest pytest-django model-bakery pytest-cov

pytest -v --cov=src --cov-report=term-missing
```

Configure `pytest.ini` (or `pyproject.toml [tool.pytest.ini_options]`):

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
pythonpath = src
```

See `.github/skills/test.md` for the full testing skill and conventions.

---

## Security Notes

- `RagCorpusView` uses `hmac.compare_digest` for constant-time token comparison.
- `RAG_INTERNAL_TOKEN` must be set; if empty, all RAG requests are denied.
- Never expose `/articles/rag-corpus/` via the public proxy.
- Django CSRF middleware is active — all state-changing requests from the browser
  must include a valid CSRF token.
- All secrets must come from environment variables. Never hardcode or commit them.
- `ruff` is the project linter; run `ruff check .` before committing.

---

## Code Editing Rules

- Follow `.github/skills/codeEdit.md` and `.github/skills/test.md`.
- Use Python type hints on all function signatures and return types.
- Follow PEP 8 via `ruff` (line-length 79).
- Keep views thin — business logic belongs in service functions or model methods.
- Register all new models in `admin.py` with meaningful `list_display` and `search_fields`.
