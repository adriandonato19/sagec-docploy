#!/bin/sh
set -e

python manage.py migrate --noinput

gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --preload \
    --access-logfile - \
    --error-logfile - &
GUNICORN_PID=$!

python -c "
import time, urllib.request, urllib.error
start = time.time()
for attempt in range(60):
    try:
        urllib.request.urlopen('http://127.0.0.1:8000/login/', timeout=15)
        elapsed = time.time() - start
        print(f'[warm-up] ready in {elapsed:.2f}s after {attempt + 1} attempt(s)', flush=True)
        break
    except (urllib.error.URLError, ConnectionError, OSError):
        time.sleep(1)
else:
    print('[warm-up] timeout after 60 attempts', flush=True)
" || true

wait $GUNICORN_PID
