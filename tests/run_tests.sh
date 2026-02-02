#!/usr/bin/env bash
set -euo pipefail

: "${SSH_HOST:=sshpoc}"
: "${SSH_PORT:=22}"
: "${KEYS_DIR:=/keys}"

mkdir -p "${KEYS_DIR}"

# Generate keys for put/get
if [ ! -f "${KEYS_DIR}/put" ]; then
  ssh-keygen -t ed25519 -N "" -f "${KEYS_DIR}/put" >/dev/null
fi
if [ ! -f "${KEYS_DIR}/get" ]; then
  ssh-keygen -t ed25519 -N "" -f "${KEYS_DIR}/get" >/dev/null
fi

cp -f "${KEYS_DIR}/put.pub" "${KEYS_DIR}/put.pub"
cp -f "${KEYS_DIR}/get.pub" "${KEYS_DIR}/get.pub"

# Wait for SSH to accept connections
for i in $(seq 1 60); do
  if nc -z "${SSH_HOST}" "${SSH_PORT}"; then
    break
  fi
  sleep 1
done

pytest -q