"""Sistema interno MOCKADO: simula o sistema separado que recebe os pedidos do worker.

Roda como serviço próprio (container `internal-system`), fora da API de recebimento:

    uvicorn internal_system.main:app --port 9000

Não usa nada do pacote `app`: é outro sistema, só se comunica por HTTP.

Cenários (pelo prefixo do externalId, sem diferenciar maiúsculas):
    FAIL-...     recusa definitiva (HTTP 422)                       -> pedido FAILED na 1ª tentativa
    FLAKY-...    indisponível (HTTP 503) nas 2 primeiras chamadas   -> PROCESSED na 3ª tentativa
    TIMEOUT-...  demora mais que o timeout do worker                -> retentativas e FAILED no fim
    OUTAGE-...   indisponível (HTTP 503) nas 3 primeiras chamadas   -> FAILED (tentativas esgotadas);
                 volta a responder depois                              reprocessado -> PROCESSED
    valor acima de INTERNAL_SYSTEM_MAX_AMOUNT: recusa definitiva (HTTP 422)
    demais:      sucesso, com falha intermitente aleatória (HTTP 503) em
                 INTERNAL_SYSTEM_FAILURE_RATE das chamadas (padrão 0 = nunca)

É idempotente pelo header `Idempotency-Key`: a mesma chave já aceita devolve o
mesmo protocolo, sem processar de novo.
"""

import asyncio
import os
import random
import uuid
from collections import Counter
from decimal import Decimal

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

FAILURE_RATE = float(os.getenv("INTERNAL_SYSTEM_FAILURE_RATE", "0"))
MIN_LATENCY_MS = int(os.getenv("INTERNAL_SYSTEM_MIN_LATENCY_MS", "100"))
MAX_LATENCY_MS = int(os.getenv("INTERNAL_SYSTEM_MAX_LATENCY_MS", "600"))
TIMEOUT_SCENARIO_SECONDS = float(os.getenv("INTERNAL_SYSTEM_TIMEOUT_SCENARIO_SECONDS", "30"))
MAX_AMOUNT = Decimal(os.getenv("INTERNAL_SYSTEM_MAX_AMOUNT", "100000"))
FLAKY_FAILURES = 2
# Igual ao ORDER_MAX_ATTEMPTS padrão: a queda dura a rodada inteira de tentativas
OUTAGE_FAILURES = int(os.getenv("INTERNAL_SYSTEM_OUTAGE_FAILURES", "3"))

app = FastAPI(
    title="Sistema interno (mock)",
    description="Simula o sistema interno que processa os pedidos. Veja os cenários no código.",
)

# Estado em memória: é um mock. Um sistema real persistiria isso.
accepted: dict[str, dict] = {}
calls: Counter[str] = Counter()


class InternalOrderRequest(BaseModel):
    order_id: int = Field(alias="orderId")
    external_id: str = Field(alias="externalId")
    customer: str
    amount: Decimal


def error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/internal/orders")
async def process_order(
    body: InternalOrderRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    key = idempotency_key or body.external_id
    if key in accepted:
        return JSONResponse(accepted[key], headers={"Idempotent-Replayed": "true"})

    calls[key] += 1
    await asyncio.sleep(random.randint(MIN_LATENCY_MS, MAX_LATENCY_MS) / 1000)

    scenario = body.external_id.upper()
    if scenario.startswith("FAIL"):
        return error(422, "Pedido recusado: cliente com cadastro bloqueado no sistema interno")
    if body.amount > MAX_AMOUNT:
        return error(422, f"Pedido recusado: valor acima do limite de {MAX_AMOUNT}")
    if scenario.startswith("TIMEOUT"):
        await asyncio.sleep(TIMEOUT_SCENARIO_SECONDS)
        return error(504, "Processamento demorou demais")
    if scenario.startswith("FLAKY") and calls[key] <= FLAKY_FAILURES:
        return error(503, f"Sistema interno temporariamente indisponível (chamada {calls[key]})")
    if scenario.startswith("OUTAGE") and calls[key] <= OUTAGE_FAILURES:
        return error(503, f"Sistema interno fora do ar (chamada {calls[key]} de {OUTAGE_FAILURES} com falha)")
    if random.random() < FAILURE_RATE:
        return error(503, "Falha intermitente simulada")

    result = {"reference": f"INT-{uuid.uuid4().hex[:8].upper()}", "status": "ACCEPTED"}
    accepted[key] = result
    return JSONResponse(result)
