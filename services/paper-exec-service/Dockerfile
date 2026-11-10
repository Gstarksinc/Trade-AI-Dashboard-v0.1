FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=UTC
WORKDIR /app
COPY services/paper-exec-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs/ /app/libs/
COPY services/paper-exec-service/ /app/services/paper-exec-service/
WORKDIR /app/services/paper-exec-service
ENV PYTHONPATH=/app
EXPOSE 8007
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8007"]
