FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=UTC
WORKDIR /app
COPY services/notifier-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs/ /app/libs/
COPY services/notifier-service/ /app/services/notifier-service/
WORKDIR /app/services/notifier-service
ENV PYTHONPATH=/app
EXPOSE 8009
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8009"]

