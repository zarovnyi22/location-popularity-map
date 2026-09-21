#!/bin/sh
set -e

echo "Waiting for the database..."
python - <<'PYEOF'
import os
import sys
import time

import psycopg2

if os.environ.get("USE_SQLITE") == "1":
    sys.exit(0)

for _ in range(30):
    try:
        psycopg2.connect(
            dbname=os.environ.get("DB_NAME", "location_map"),
            user=os.environ.get("DB_USER", "location_map"),
            password=os.environ.get("DB_PASSWORD", "location_map"),
            host=os.environ.get("DB_HOST", "db"),
            port=os.environ.get("DB_PORT", "5432"),
        ).close()
        sys.exit(0)
    except psycopg2.OperationalError:
        time.sleep(1)

print("Database never became available", file=sys.stderr)
sys.exit(1)
PYEOF

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
