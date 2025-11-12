# Dockerfile for AI-CTI Backend API
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Create necessary directories
RUN mkdir -p data_results data_ingest/processed data_ingest/raw

# Expose port (Railway/Render will set PORT env var)
EXPOSE 8000

# Use PORT environment variable if set, otherwise default to 8000
CMD python -m uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
