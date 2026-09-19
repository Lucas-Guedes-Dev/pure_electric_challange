"""Handler de logging que envia os registros para o Elasticsearch (visualizados no Kibana).

Os logs viram documentos no formato ECS (Elastic Common Schema) e são gravados no data
stream `logs-<dataset>-<namespace>`, que usa o template de logs nativo do Elasticsearch.

O envio nunca pode atrapalhar a API:
- `emit()` só coloca o documento numa fila em memória (não faz I/O no request);
- uma thread em segundo plano envia em lotes pelo endpoint `_bulk`;
- se o Elasticsearch estiver fora (ex.: ainda subindo), o lote é reenviado depois;
- antes do 1º envio garante que o data stream existe. Sem isso, se a API mandar logs
  antes de o Elasticsearch terminar de instalar o template `logs-*-*` (ele faz isso em
  segundo plano após subir), o destino vira um índice comum, com os campos mal tipados;
- com a fila cheia, os logs novos são descartados em vez de consumir memória sem limite.
"""

import copy
import json
import logging
import queue
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

ECS_VERSION = "8.11.0"


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
    return target


class ElasticsearchLogHandler(logging.Handler):
    def __init__(
        self,
        url: str,
        data_stream: str,
        *,
        service_name: str,
        service_version: str,
        environment: str,
        batch_size: int = 200,
        flush_interval: float = 2.0,
        retry_delay: float = 5.0,
        queue_size: int = 10_000,
        timeout: float = 5.0,
    ) -> None:
        super().__init__()
        self._base_url = url.rstrip("/")
        self._data_stream = data_stream
        self._data_stream_ready = False
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._retry_delay = retry_delay
        self._timeout = timeout
        self._base_fields = {
            "ecs": {"version": ECS_VERSION},
            "service": {"name": service_name, "version": service_version, "environment": environment},
            "host": {"name": socket.gethostname()},
        }
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=queue_size)
        self._stop = threading.Event()
        self._last_warning = float("-inf")
        self._thread = threading.Thread(target=self._run, name="elasticsearch-log-shipper", daemon=True)
        self._thread.start()

    # --- lado da aplicação: rápido e sem I/O -------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        try:
            document = self.to_document(record)
        except Exception:
            self.handleError(record)
            return
        try:
            self._queue.put_nowait(document)
        except queue.Full:
            self._warn("fila de logs cheia; descartando registros até o Elasticsearch responder")

    def to_document(self, record: logging.LogRecord) -> dict[str, Any]:
        document: dict[str, Any] = copy.deepcopy(self._base_fields)
        document |= {
            "@timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "message": record.getMessage(),
            "log": {
                "level": record.levelname,
                "logger": record.name,
                "origin": {
                    "file": {"name": record.pathname, "line": record.lineno},
                    "function": record.funcName,
                },
            },
            "process": {"pid": record.process, "thread": {"name": record.threadName}},
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            _deep_merge(document, {"http": {"request": {"id": request_id}}})

        if record.exc_info and record.exc_info[1] is not None:
            exc_type, exc, tb = record.exc_info
            document["error"] = {
                "type": exc_type.__name__ if exc_type else type(exc).__name__,
                "message": str(exc),
                "stack_trace": "".join(traceback.format_exception(exc_type, exc, tb)),
            }

        # Campos estruturados passados com logger.info(..., extra={"ecs": {...}})
        extra = getattr(record, "ecs", None)
        if isinstance(extra, dict):
            _deep_merge(document, extra)
        return document

    # --- thread de envio ---------------------------------------------------------------

    def _run(self) -> None:
        batch: list[dict[str, Any]] = []
        while not self._stop.is_set():
            if not batch:
                batch = self._collect(wait=True)
            if batch and not self._send(batch):
                # Elasticsearch fora: segura o lote e tenta de novo depois
                self._stop.wait(self._retry_delay)
                continue
            batch = []

        # Encerrando: uma última tentativa com o que sobrou na fila
        batch += self._collect(wait=False)
        while batch:
            if not self._send(batch):
                break
            batch = self._collect(wait=False)

    def _collect(self, *, wait: bool) -> list[dict[str, Any]]:
        """Junta até `batch_size` documentos, esperando no máximo `flush_interval`."""
        batch: list[dict[str, Any]] = []
        deadline = time.monotonic() + self._flush_interval
        while len(batch) < self._batch_size:
            remaining = deadline - time.monotonic()
            try:
                if wait and remaining > 0:
                    batch.append(self._queue.get(timeout=remaining))
                else:
                    batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
            if self._stop.is_set():
                wait = False
        return batch

    def _http(self, method: str, path: str, body: bytes | None = None) -> tuple[int, dict[str, Any]]:
        """Chamada ao Elasticsearch. Erros de rede sobem como URLError/OSError."""
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/x-ndjson" if path.endswith("_bulk") else "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return response.status, json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            try:
                error_body = json.loads(exc.read() or b"{}")
            except ValueError:
                error_body = {}
            return exc.code, error_body

    def _ensure_data_stream(self) -> bool:
        """Cria o data stream se ainda não existir. False = tentar de novo mais tarde."""
        if self._data_stream_ready:
            return True

        path = f"/_data_stream/{self._data_stream}"
        if self._http("GET", path)[0] != 200:
            status, body = self._http("PUT", path)
            error = body.get("error")
            error_type = error.get("type") if isinstance(error, dict) else None
            if status == 200:
                pass
            elif error_type == "resource_already_exists_exception":
                # Outro processo (ex.: um worker) criou antes: ok. Ou já existe um índice
                # comum com esse nome: envia assim mesmo para não perder logs, mas avisa.
                if self._http("GET", path)[0] != 200:
                    self._warn(
                        f"'{self._data_stream}' existe como índice comum, não como data stream: "
                        "apague-o no Elasticsearch para os campos ficarem tipados corretamente"
                    )
            else:
                # Normalmente: o template logs-*-* ainda não foi instalado (ES acabou de subir)
                self._warn(f"data stream '{self._data_stream}' ainda não pode ser criado ({status}): {error}")
                return False

        self._data_stream_ready = True
        return True

    def _send(self, batch: list[dict[str, Any]]) -> bool:
        """Envia o lote. Retorna False quando vale a pena tentar de novo."""
        lines = []
        for document in batch:
            lines.append('{"create":{}}')
            lines.append(json.dumps(document, default=str, ensure_ascii=False))
        body = ("\n".join(lines) + "\n").encode("utf-8")
        try:
            if not self._ensure_data_stream():
                return False
            status, result = self._http("POST", f"/{self._data_stream}/_bulk", body)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self._warn(f"Elasticsearch indisponível ({exc}); os logs serão reenviados")
            return False

        if status >= 400:
            self._warn(f"Elasticsearch respondeu {status} ao receber logs: {result}")
            # 4xx = documento inválido: reenviar não resolve
            return status < 500 and status != 429

        if result.get("errors"):
            reason = next(
                (item["create"].get("error") for item in result.get("items", []) if "error" in item.get("create", {})),
                None,
            )
            self._warn(f"alguns logs foram rejeitados pelo Elasticsearch: {reason}")
        return True

    def _warn(self, message: str) -> None:
        # Direto no stderr e no máximo 1x por minuto: usar o logging aqui geraria um loop
        now = time.monotonic()
        if now - self._last_warning >= 60:
            self._last_warning = now
            print(f"[elasticsearch-log-handler] {message}", file=sys.stderr)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=self._timeout + 1)
        super().close()
