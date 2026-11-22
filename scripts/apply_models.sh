#!/usr/bin/env bash
# Застосовує всі SQL-моделі до бази. Використання: ./scripts/apply_models.sh [назва_бази]
set -euo pipefail
set -a; source .env; set +a
DB="${1:-$POSTGRES_DB}"
for f in sql/models/*.sql; do
  echo "-> $f"
  docker exec -i etsy_db psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$DB" < "$f"
done
echo "готово: $DB"
