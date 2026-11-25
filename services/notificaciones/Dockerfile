# Notificaciones microservice image (Sprint 5).
# Build context is the repository root:  docker build -f services/notificaciones/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The service reuses the shared/ package (database + security modules)
# from the repository root.
COPY shared/ shared/
COPY services/notificaciones/ services/notificaciones/

WORKDIR /app/services/notificaciones
EXPOSE 8005

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
