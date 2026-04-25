FROM node:20-slim AS h5-builder

WORKDIR /workspace/apps/h5
COPY apps/h5/package*.json ./
RUN npm ci
COPY apps/h5/ ./
RUN npm run build

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .
COPY --from=h5-builder /workspace/apps/h5/dist /app/app/static/h5

# Expose port
EXPOSE 8001

# Run the application
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
