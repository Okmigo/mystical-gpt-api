# Use Python slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy all app files
COPY . .

# Install system-level dependencies
RUN apt-get update && apt-get install -y gcc libglib2.0-0 libsm6 libxrender1 libxext6 && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port for Cloud Run
EXPOSE 8080

# Start the app using Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:gunicorn_app"]
