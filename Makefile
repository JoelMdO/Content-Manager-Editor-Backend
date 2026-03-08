.PHONY: help up down build logs shell-django shell-db migrate backup restore

help:
	@echo ""
	@echo "  make up           — start all services"
	@echo "  make down         — stop (volumes preserved)"
	@echo "  make build        — rebuild all images"
	@echo "  make logs         — tail all logs"
	@echo "  make migrate      — run Django migrations"
	@echo "  make shell-django — open Django shell"
	@echo "  make shell-db     — open psql"
	@echo "  make superuser    — create Django superuser"
	@echo ""

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build --no-cache

logs:
	docker compose logs -f

migrate:
	docker compose exec django python manage.py migrate

shell-django:
	docker compose exec django python manage.py shell

shell-db:
	docker compose exec db psql -U $${DB_USER:-postgres} -d $${DB_NAME:-blog_db}

superuser:
	docker compose exec django python manage.py createsuperuser

update-django:
	docker compose build django
	docker compose up -d --no-deps django
