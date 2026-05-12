#!/bin/sh
set -e

python manage.py migrate --noinput

gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --preload &
GUNICORN_PID=$!

python -c "
import time, urllib.request, urllib.error
for attempt in range(60):
    try:
        urllib.request.urlopen('http://127.0.0.1:8000/login/', timeout=5)
        print(f'[warm-up] gunicorn reachable after {attempt + 1} attempt(s)', flush=True)
        break
    except (urllib.error.URLError, ConnectionError, OSError):
        time.sleep(1)
else:
    print('[warm-up] gave up waiting for gunicorn', flush=True)

for i in range(10):
    try:
        urllib.request.urlopen('http://127.0.0.1:8000/login/', timeout=15)
    except Exception as e:
        print(f'[warm-up] request {i + 1} failed: {e}', flush=True)
print('[warm-up] complete', flush=True)
" || true

wait $GUNICORN_PID
