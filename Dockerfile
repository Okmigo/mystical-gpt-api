# Dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# EXPOSE must match Cloud Run default PORT=8080
EXPOSE 8080

# Start the Flask app with host/port explicitly set
CMD ["python", "drive_search_api.py"]
