# Auth microservice image (Sprint 2).
# Build context is the repository root:  docker build -f services/auth/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The service reuses the shared/ package (database + security modules)
# from the repository root.
COPY shared/ shared/
COPY services/auth/ services/auth/

WORKDIR /app/services/auth
EXPOSE 8004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
