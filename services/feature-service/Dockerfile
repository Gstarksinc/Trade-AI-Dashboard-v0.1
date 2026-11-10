FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=UTC
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl ca-certificates libgomp1 && rm -rf /var/lib/apt/lists/*
ARG TALIB_VERSION=0.6.4
RUN curl -fsSL https://github.com/ta-lib/ta-lib/releases/download/v${TALIB_VERSION}/ta-lib-${TALIB_VERSION}-src.tar.gz -o /tmp/ta-lib.tar.gz && tar -xzf /tmp/ta-lib.tar.gz -C /tmp && cd /tmp/ta-lib-${TALIB_VERSION} && ./configure --prefix=/usr && make -j$(nproc) && make install && rm -rf /tmp/ta-lib*
WORKDIR /app
COPY services/feature-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs/ /app/libs/
COPY services/feature-service/ /app/services/feature-service/
WORKDIR /app/services/feature-service
ENV PYTHONPATH=/app
EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
