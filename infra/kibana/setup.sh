#!/bin/sh
# Configura o Kibana na primeira subida (idempotente: pode rodar de novo sem problema).
# Cria o data view dos logs da API e o define como padrão, para abrir o Discover já com os logs.
set -e

KIBANA_URL="${KIBANA_URL:-http://kibana:5601}"
DATA_VIEW_ID="pure-eletric-api-logs"

# Na 1ª subida, com pouca RAM, o Kibana pode levar mais de 10 minutos
TIMEOUT_SECONDS="${KIBANA_SETUP_TIMEOUT_SECONDS:-1800}"

echo "Aguardando o Kibana ficar disponível (até $((TIMEOUT_SECONDS / 60)) min)..."
waited=0
until curl -fsS -m 10 "$KIBANA_URL/api/status" 2>/dev/null | grep -q '"level":"available"'; do
  if [ "$waited" -ge "$TIMEOUT_SECONDS" ]; then
    echo "Kibana não ficou disponível a tempo. Veja: docker compose logs kibana" >&2
    exit 1
  fi
  sleep 10
  waited=$((waited + 10))
done

echo "Criando o data view dos logs da API..."
curl -fsS -X POST "$KIBANA_URL/api/data_views/data_view" \
  -H "kbn-xsrf: true" -H "Content-Type: application/json" \
  -d '{
    "override": true,
    "data_view": {
      "id": "'"$DATA_VIEW_ID"'",
      "name": "API Pure Eletric - logs",
      "title": "logs-pure_eletric.api-*",
      "timeFieldName": "@timestamp"
    }
  }' > /dev/null

curl -fsS -X POST "$KIBANA_URL/api/data_views/default" \
  -H "kbn-xsrf: true" -H "Content-Type: application/json" \
  -d '{"data_view_id": "'"$DATA_VIEW_ID"'", "force": true}' > /dev/null

echo "Kibana pronto: http://localhost:${KIBANA_PORT:-5601}/app/discover"
