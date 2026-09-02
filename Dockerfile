FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/domains/education:/app/platform/kernel:/app/platform/api:/app/platform/worker

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt .

RUN pip install --no-cache-dir \
    -r requirements-prod.txt

COPY platform ./platform
COPY domains/education ./domains/education

RUN useradd --create-home --uid 10001 rkjo \
    && chown -R rkjo:rkjo /app

USER rkjo

CMD ["python", "-m", "rkjo_worker.main"]
