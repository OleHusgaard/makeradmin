#!/bin/bash
set -e

function wait_for {
    local host="$1"
    local port="$2"
    for i in $(seq 1 100); do
        if nc -z "$host" "$port"; then
            return
        fi
        sleep 0.2
    done
    echo "wait for $host:$port timed out"
    exit 1
}

wait_for "${MYSQL_HOST%%:*}" "${MYSQL_HOST##*:}"
wait_for api-gateway 80

echo "migrating"
python3 src/migrate.py --assert-up-to-date

GUNICORN_FLAGS=""

if [ "$APP_DEBUG" = "true" ]; then
    echo "running app in devel mode"
    GUNICORN_FLAGS=" --reload"
fi

# Note: for some reason the workers seem to sometimes get blocked by persistent connections
# (many browsers keep persistent connections to servers just in case they need them later).
# The gthread worker class should help with this, but it doesn't always seem to work for some reason.
# However running the servers behind nginx (and using the sync class) resolves all problems
# as nginx handles all the persistent connections.
echo "starting gunicorn"
exec gunicorn $GUNICORN_FLAGS --access-logfile - --worker-class sync --workers=5 -b :80 src.app:app
