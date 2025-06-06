# syntax=docker/dockerfile:1

FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y \
    gcc libglib2.0-0 libsm6 libxrender1 libxext6 \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

# Gunicorn entrypoint targeting `gunicorn_app` inside `main.py`
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:gunicorn_app"]
