# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the model into /app directory
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2').save('./models/all-MiniLM-L6-v2')"

# Expose app
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8080", "app:app"]
