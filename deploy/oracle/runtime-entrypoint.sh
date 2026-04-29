#!/usr/bin/env sh
set -eu

# Docker named volumes can be mounted as root-owned even when the image has
# app-owned directories. Repair only runtime write paths, then drop privileges.
chown -R audioraq:audioraq /app/data /app/memory 2>/dev/null || true

exec gosu audioraq "$@"
