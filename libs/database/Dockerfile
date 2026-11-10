FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=UTC
WORKDIR /app
COPY libs/database/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs/ /app/libs/
ENV PYTHONPATH=/app
CMD ["alembic", "-c", "libs/database/alembic.ini", "upgrade", "head"]
