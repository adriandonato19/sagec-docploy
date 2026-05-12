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
        print(f'[warm-up] ready after {attempt + 1} attempt(s)', flush=True)
        break
    except (urllib.error.URLError, ConnectionError, OSError):
        time.sleep(1)
else:
    print('[warm-up] gave up after 60s', flush=True)
" || true

wait $GUNICORN_PID
