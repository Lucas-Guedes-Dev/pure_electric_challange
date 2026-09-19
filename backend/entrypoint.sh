#!/bin/sh
set -e

echo "Aplicando migrations..."
alembic upgrade head

exec "$@"
