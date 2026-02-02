#!/usr/bin/env bash
set -euo pipefail

: "${DATA_DIR:=/data}"
: "${KEYS_DIR:=/keys}"
: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_NAME:=poc}"
: "${DB_USER:=poc}"
: "${DB_PASSWORD:=poc}"
: "${SSHD_LOG_LEVEL:=INFO}"

mkdir -p "${DATA_DIR}"
chmod 755 "${DATA_DIR}"

# Host keys (generate if absent)
if [ ! -f /etc/ssh/ssh_host_ed25519_key ]; then
  ssh-keygen -A >/dev/null 2>&1
fi

# Wait for keys (tests generate these into shared volume)
mkdir -p /home/put/.ssh /home/get/.ssh
chmod 700 /home/put/.ssh /home/get/.ssh
chown -R put:put /home/put/.ssh
chown -R get:get /home/get/.ssh

if [ -f "${KEYS_DIR}/put.pub" ]; then
  cat "${KEYS_DIR}/put.pub" > /home/put/.ssh/authorized_keys
  chmod 600 /home/put/.ssh/authorized_keys
  chown put:put /home/put/.ssh/authorized_keys
fi

if [ -f "${KEYS_DIR}/get.pub" ]; then
  cat "${KEYS_DIR}/get.pub" > /home/get/.ssh/authorized_keys
  chmod 600 /home/get/.ssh/authorized_keys
  chown get:get /home/get/.ssh/authorized_keys
else
  echo "WARN: missing ${KEYS_DIR}/get.pub (download user will be disabled until provided)" >&2
fi

# Initialize DB schema (idempotent)
export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
python -c "from app.db import init_db; init_db()"

cat > /etc/ssh/sshd_env <<EOF
export DB_HOST=${DB_HOST}
export DB_PORT=${DB_PORT}
export DB_NAME=${DB_NAME}
export DB_USER=${DB_USER}
export DB_PASSWORD=${DB_PASSWORD}
export DATA_DIR=${DATA_DIR}
export TTL_DAYS=${TTL_DAYS}
export POC_LOG_LEVEL=${POC_LOG_LEVEL:-}
EOF

echo "STARTED"

# Start sshd in foreground
exec /usr/sbin/sshd -D -e
