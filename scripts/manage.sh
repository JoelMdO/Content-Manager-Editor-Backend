#!/usr/bin/env bash
set -euo pipefail

# Helper for common docker compose tasks for this repo
# Usage: ./scripts/manage.sh <command>
# Commands: create-volumes | up | migrate | createsuperuser | shell | rebuild | down

COMPOSE="docker compose"
VOLUMES=(postgres_data django_media django_static)

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 {create-volumes|up|migrate|createsuperuser|shell|rebuild|down}"
  exit 1
fi

cmd="$1"

case "$cmd" in
  create-volumes)
    echo "Creating named volumes: ${VOLUMES[*]}"
    for v in "${VOLUMES[@]}"; do
      docker volume create "$v" >/dev/null || true
      echo "- $v"
    done
    ;;

  up)
    echo "Starting db and web services"
    $COMPOSE up -d db web
    ;;

  migrate)
    echo "Running migrations in web"
    $COMPOSE exec web python manage.py migrate
    ;;

  createsuperuser)
    echo "Creating superuser in web"
    $COMPOSE exec web python manage.py createsuperuser
    ;;

  shell)
    echo "Opening shell in web"
    # prefer bash, fallback to sh
    if $COMPOSE exec web bash -c 'echo ok' >/dev/null 2>&1; then
      $COMPOSE exec web bash
    else
      $COMPOSE exec web sh
    fi
    ;;

  rebuild)
    echo "Rebuilding django image and restarting web (volumes preserved)"
    $COMPOSE build django
    $COMPOSE up -d --no-deps --build web
    ;;

  down)
    echo "Stopping services (volumes will be kept). To remove volumes use: 'docker compose down -v'"
    $COMPOSE down
    ;;

  *)
    echo "Unknown command: $cmd"
    echo "Usage: $0 {create-volumes|up|migrate|createsuperuser|shell|rebuild|down}"
    exit 2
    ;;
esac

exit 0
