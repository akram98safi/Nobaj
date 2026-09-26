# Multi-stage Dockerfile for Nobaj Media Platform
FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies & latest FFmpeg with hardware acceleration drivers
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libva-drm2 \
    va-driver-all \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy source code
COPY backend /app/backend
COPY frontend /app/frontend

# Create data directories with appropriate permissions
RUN mkdir -p /app/data/uploads /app/data/outputs /app/data/temp && \
    useradd -m -u 1000 nobaj && \
    chown -R nobaj:nobaj /app

USER nobaj

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
