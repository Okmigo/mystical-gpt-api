# File: Dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y gcc libglib2.0-0 libsm6 libxrender1 libxext6 && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:gunicorn_app"]
