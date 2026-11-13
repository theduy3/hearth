#!/usr/bin/env bash
# Enter the existing Hermes namespaces while keeping this service's cgroup.
# docker exec processes belong to Docker's cgroup and survive its client exit.
set -euo pipefail
hermes_pid="$(/usr/bin/docker inspect --format '{{.State.Pid}}' hermes)"
[[ "$hermes_pid" =~ ^[1-9][0-9]*$ ]] || { echo 'Hermes container is not running' >&2; exit 1; }
exec /usr/bin/nsenter --target "$hermes_pid" --mount --uts --ipc --net --pid \
  --root --wd="/proc/$hermes_pid/root/home/hermes/.hermes/catthew-terminal" --setgid 1500 --setuid 1500 \
  /home/hermes/.hermes/hermes-agent/venv/bin/python -m hub.terminal \
  --state /home/hermes/.hermes/catthew-terminal-state \
  --profile /home/hermes/.hermes/profiles/catthew --vault /vault
