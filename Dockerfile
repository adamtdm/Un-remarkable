FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RMC_DATA_DIR=/data \
    RMC_HOST=0.0.0.0 \
    RMC_PORT=8099

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Create non-root user and data volume
RUN useradd -u 1000 -m -s /bin/bash rmc && \
    mkdir -p /data && \
    chown -R rmc:rmc /app /data

USER rmc
VOLUME ["/data"]

EXPOSE 8099

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8099/api/status || exit 1

ENTRYPOINT ["rmcompanion"]
CMD ["run"]
