# Place this file at backend/Dockerfile in your repo.
FROM python:3.11-slim

WORKDIR /app

# System deps for common ML libs (xgboost, scikit-learn wheels usually don't need build tools,
# but keep gcc available in case any dependency needs to compile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app/ ./app/
COPY artifacts/ ./artifacts/
COPY knowledge/ ./knowledge/

RUN pip install --no-cache-dir -e .

# Cloud Run injects $PORT; default to 8080 to match cloud_run.tf's container_port
ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
