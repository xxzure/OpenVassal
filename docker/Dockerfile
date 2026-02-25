FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for caching
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Default command
CMD ["subordinates"]
