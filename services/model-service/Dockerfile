FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=UTC
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY services/model-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs/ /app/libs/
COPY services/model-service/ /app/services/model-service/
WORKDIR /app/services/model-service
ENV PYTHONPATH=/app
EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
