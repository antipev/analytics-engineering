#!/bin/sh
set -eu

# Wait for the Dagster webserver before nginx starts accepting traffic.
until curl -fsS http://127.0.0.1:3000/server_info >/dev/null 2>&1; do
    sleep 1
done

exec /usr/sbin/nginx -c /tmp/nginx.conf -g 'daemon off;'
