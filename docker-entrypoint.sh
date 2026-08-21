#!/bin/sh
set -eu

CRONTAB="${CRONTAB:-/app/crontab}"

case "${RUN_ON_START:-false}" in
  1|true|TRUE|True|yes|YES)
    echo "entrypoint: RUN_ON_START set, running once before scheduling"
    # Deliberately non-fatal: a store API being down at deploy time must not
    # leave the container in a crash loop with no scheduler running.
    python main.py || echo "entrypoint: initial run failed, continuing to schedule"
    ;;
esac

echo "entrypoint: starting supercronic with $CRONTAB"
exec supercronic "$CRONTAB"
