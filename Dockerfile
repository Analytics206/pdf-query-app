# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if needed)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Copy the requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- CORRECTED CODE COPY ---
# Copy the application code from host's ./app directory to container's /app directory
COPY ./app /app

# Copy the placeholder directories (ensures paths exist in image before volume mount)
COPY ./uploads /app/uploads
COPY ./data /app/data

# Expose the port the app runs on
EXPOSE 8000

# --- CORRECTED CMD ---
# Run uvicorn, looking for 'app' object in 'main.py' directly within WORKDIR (/app)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]