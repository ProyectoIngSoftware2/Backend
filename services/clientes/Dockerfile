# Clientes microservice image.
# Build context is the repository root:  docker build -f services/clientes/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The service reuses the shared/ database module from the repository root.
COPY shared/ shared/
COPY services/clientes/ services/clientes/

WORKDIR /app/services/clientes
EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
