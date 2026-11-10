FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=UTC
WORKDIR /app
COPY services/market-collector/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs/ /app/libs/
COPY services/market-collector/ /app/services/market-collector/
WORKDIR /app/services/market-collector
ENV PYTHONPATH=/app
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
