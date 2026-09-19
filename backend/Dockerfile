FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY . .

EXPOSE 8000

ENTRYPOINT ["sh", "./entrypoint.sh"]
# PORT: definida pelo Railway (e outras plataformas); 8000 localmente.
# FORWARDED_ALLOW_IPS (lida pelo uvicorn): de quem aceitar X-Forwarded-For (IP real no rate limit)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
