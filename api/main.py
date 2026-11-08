import os

import psycopg
import redis
from fastapi import FastAPI

app = FastAPI(title='Signals API')


@app.get('/health')
def health():
    status = {'api': 'ok'}
    try:
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:
            conn.execute('SELECT 1')
        status['db'] = 'ok'
    except Exception as e:
        status['db'] = 'error: ' + type(e).__name__
    try:
        redis.from_url(os.environ['REDIS_URL']).ping()
        status['redis'] = 'ok'
    except Exception as e:
        status['redis'] = 'error: ' + type(e).__name__
    return status
