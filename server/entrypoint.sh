#!/usr/bin/env bash
set -euo pipefail

: "${LOG_LEVEL:=INFO}"
: "${LOG_SINK:=/var/log/gateway.log}"

log_level_num() {
  case "${1}" in
    ERROR) echo 0 ;;
    WARNING|WARN) echo 1 ;;
    INFO) echo 2 ;;
    DEBUG) echo 3 ;;
    VERBOSE|TRACE) echo 4 ;;
    *) echo 2 ;;
  esac
}

should_log() {
  [ "$(log_level_num "${1}")" -le "$(log_level_num "${LOG_LEVEL}")" ]
}

log() {
  level="${1}"
  shift
  if should_log "${level}"; then
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "${level} ${ts} $*" >&2
  fi
}

log_error() { log ERROR "$*"; }
log_warn() { log WARNING "$*"; }
log_info() { log INFO "$*"; }
log_debug() { log DEBUG "$*"; }
log_verbose() { log VERBOSE "$*"; }

: "${DATA_DIR:=/data}"
: "${KEYS_DIR:=/keys}"
: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_NAME:=app}"
: "${DB_USER:=app}"
: "${DB_PASSWORD:=app}"
: "${SSHD_LOG_LEVEL:=INFO}"

log_info "entrypoint starting LOG_LEVEL=${LOG_LEVEL}"
log_debug "env DATA_DIR=${DATA_DIR} KEYS_DIR=${KEYS_DIR} DB_HOST=${DB_HOST} DB_PORT=${DB_PORT} DB_NAME=${DB_NAME} DB_USER=${DB_USER}"

mkdir -p /var/log
touch "${LOG_SINK}"
chmod 666 "${LOG_SINK}"
tail -n+1 -F "${LOG_SINK}" >&2 &

mkdir -p "${DATA_DIR}"
chmod 755 "${DATA_DIR}"

# Host keys (generate if absent)
if [ ! -f /etc/ssh/ssh_host_ed25519_key ]; then
  log_info "generating ssh host keys"
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
  log_info "loaded put.pub"
fi

if [ -f "${KEYS_DIR}/get.pub" ]; then
  cat "${KEYS_DIR}/get.pub" > /home/get/.ssh/authorized_keys
  chmod 600 /home/get/.ssh/authorized_keys
  chown get:get /home/get/.ssh/authorized_keys
  log_info "loaded get.pub"
else
  log_warn "missing ${KEYS_DIR}/get.pub (download user will be disabled until provided)"
fi

# Initialize DB schema (idempotent)
export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
log_info "initializing database schema"
python -c "from app.db import init_db; init_db()"

cat > /etc/ssh/sshd_env <<EOF
export DB_HOST=${DB_HOST}
export DB_PORT=${DB_PORT}
export DB_NAME=${DB_NAME}
export DB_USER=${DB_USER}
export DB_PASSWORD=${DB_PASSWORD}
export DATA_DIR=${DATA_DIR}
export TTL_DAYS=${TTL_DAYS}
export LOG_LEVEL=${LOG_LEVEL}
export LOG_SINK=${LOG_SINK}
EOF

log_info "sshd environment captured"
log_info "STARTED"

# Start sshd in foreground
exec /usr/sbin/sshd -D -e
