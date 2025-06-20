# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (needed for some PDF libs)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy all code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformers model
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2').save('/tmp/models/all-MiniLM-L6-v2')"

# Expose app
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8080", "app:app"]
