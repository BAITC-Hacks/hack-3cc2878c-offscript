# Build context = repo root (see docker-compose.yml)
FROM python:3.11-slim
WORKDIR /app
COPY ml/requirements.txt ml/requirements.txt
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY ml ml
RUN pip install --no-cache-dir -e ml
COPY backend backend
COPY shared shared
COPY data data
ENV PYTHONPATH=/app/backend:/app/ml
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
