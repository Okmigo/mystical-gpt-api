# Use an official Python runtime
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy all contents to container
COPY . .

# Install system dependencies
RUN apt-get update && apt-get install -y gcc libglib2.0-0 libsm6 libxrender1 libxext6 && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8080
EXPOSE 8080

# Start the application
CMD ["python", "main.py"]