# Use the official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy the current directory contents into the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on
EXPOSE 8080

# Run the application
CMD ["python", "app.py"]