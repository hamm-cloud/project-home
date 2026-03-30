FROM python:3.11-slim

WORKDIR /app

# Copy backend requirements
COPY backend/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Expose port
EXPOSE 8000

# Start server — Railway sets PORT env var, default to 8000
CMD uvicorn main:socket_app --host 0.0.0.0 --port ${PORT:-8000}
