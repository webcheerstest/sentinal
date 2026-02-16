FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Default port - Railway overrides this with its own PORT
ENV PORT=8080
EXPOSE 8080

# Start command - must use shell form for variable expansion
CMD ["/bin/sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
