# FactSense MES / IIoT Web Application - Production Containerfile
FROM python:3.13-slim

# Set environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install system dependencies (build-essential, libpq for PostgreSQL, font libraries for ReportLab)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libfreetype6-dev \
    libjpeg-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create working directory and unprivileged user
WORKDIR /app
RUN addgroup --system factsense && adduser --system --group factsense

# Install Python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . /app/

# Ensure runtime directories exist with proper ownership
RUN mkdir -p /app/staticfiles /app/media && \
    chown -R factsense:factsense /app

# Switch to unprivileged user
USER factsense

# Expose port
EXPOSE 8000

# Health check probe using the /healthz/ endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz/ || exit 1

# Default entrypoint
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "factsense.wsgi:application"]

