# Multi-Model RAG System Dockerfile
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ffmpeg \
    build-essential \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application
COPY backend/ /app/backend/
COPY Frontend/ /app/Frontend/
COPY README.md /app/

# Create directories
RUN mkdir -p /app/backend/models \
    /app/backend/data/datasets \
    /app/backend/data/index \
    /app/backend/logs

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

EXPOSE 8000

CMD ["python", "backend/main.py"]
