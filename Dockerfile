FROM python:3.11-slim

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Bratislava \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
      tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY app ./app

# Start script (kept at repo root)
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Runtime dir if you write data (tokens, cache, etc.)
RUN mkdir -p /data

# Documented port (Railway will inject $PORT at runtime)
EXPOSE 8080

# Use the script; it must read $PORT internally (e.g., PORT=${PORT:-8080})
CMD ["/bin/bash", "-lc", "/app/start.sh"]
