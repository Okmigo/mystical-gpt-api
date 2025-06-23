# Dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY . /app

RUN apt-get update && apt-get install -y build-essential poppler-utils git \
 && pip install --no-cache-dir -r requirements.txt \
 && rm -rf /root/.cache

CMD exec gunicorn --bind :8080 --timeout 600 --workers 1 --threads 8 app:app
