# Dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY . /app

# Add build tools for psutil and general dependencies
RUN apt-get update && \
    apt-get install -y build-essential gcc git && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /root/.cache

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--timeout", "900", "--worker-class=gthread"]
