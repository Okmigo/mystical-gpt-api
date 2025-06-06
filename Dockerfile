# Use official Python slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy app code to container
COPY . .

# Install system dependencies
RUN apt-get update && apt-get install -y gcc libglib2.0-0 libsm6 libxrender1 libxext6 && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Python requirements
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expose Cloud Run default port
EXPOSE 8080

# Start using Gunicorn via the object 'gunicorn_app'
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:gunicorn_app"]
