#!/usr/bin/env sh
set -eu

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
    echo "${level} ${ts} WRAPPER $*" >>"${LOG_SINK}"
  fi
}

log_error() { log ERROR "$*"; }
log_warn() { log WARNING "$*"; }
log_info() { log INFO "$*"; }
log_debug() { log DEBUG "$*"; }
log_verbose() { log VERBOSE "$*"; }

log_info "start user=${USER:-unknown} argv=$* SSH_ORIGINAL_COMMAND=${SSH_ORIGINAL_COMMAND:-<empty>}"

# Load env captured at container startup (sshd may not pass it through).
if [ -f /etc/ssh/sshd_env ]; then
  # shellcheck disable=SC1091
  . /etc/ssh/sshd_env
  log_info "loaded /etc/ssh/sshd_env"
fi

log_debug "env LOG_LEVEL=${LOG_LEVEL:-<unset>} DATA_DIR=${DATA_DIR:-<unset>} DB_HOST=${DB_HOST:-<unset>} PWD=${PWD:-<unset>}"

# Ensure /srv is on the module path regardless of cwd.
export PYTHONPATH="/srv:${PYTHONPATH:-}"

# Send Python logs to docker logs, not the SSH client.
export LOG_SINK

exec /usr/local/bin/python /srv/app/gateway.py "$@"
