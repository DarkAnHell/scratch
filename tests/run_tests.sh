#!/usr/bin/env bash
set -euo pipefail

: "${SSH_HOST:=sshgateway}"
: "${SSH_PORT:=22}"
: "${KEYS_DIR:=/keys}"

mkdir -p "${KEYS_DIR}"

generate_key() {
  name="$1"
  if [ ! -f "${KEYS_DIR}/${name}" ]; then
    ssh-keygen -t ed25519 -N "" -f "${KEYS_DIR}/${name}" >/dev/null
  fi
}

# Generate keys for put/get.
generate_key "put"
generate_key "get"

# Wait for SSH to accept connections
for _ in {1..60}; do
  if nc -z "${SSH_HOST}" "${SSH_PORT}"; then
    break
  fi
  sleep 1
done

pytest -q
