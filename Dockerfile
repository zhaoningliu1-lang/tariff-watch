FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[full]"

# Copy source
COPY src/ src/
COPY config.example.yaml .
COPY sample_data/ sample_data/

# Non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Expose API port
EXPOSE 8000

CMD ["uvicorn", "tariff_watch.api:app", "--host", "0.0.0.0", "--port", "8000"]
