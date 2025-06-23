FROM python:3.10-slim

WORKDIR /app

COPY . /app

RUN apt-get update && \
    apt-get install -y build-essential poppler-utils git && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--timeout", "900", "--worker-class=gthread"]
