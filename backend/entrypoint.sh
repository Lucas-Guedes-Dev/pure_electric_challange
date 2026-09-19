#!/bin/sh
set -e

# Só a API aplica as migrations. Worker e sistema interno usam RUN_MIGRATIONS=false
# (no compose eles nem passam por aqui: entrypoint vazio).
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Aplicando migrations..."
  alembic upgrade head
fi

exec "$@"
