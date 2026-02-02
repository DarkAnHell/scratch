#!/usr/bin/env sh
set -eu

log() {
  msg="$1"
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "WRAPPER $ts $msg" >&2
}

log "start user=${USER:-unknown} argv=$* SSH_ORIGINAL_COMMAND=${SSH_ORIGINAL_COMMAND:-<empty>}"

# Load env captured at container startup (sshd may not pass it through).
if [ -f /etc/ssh/sshd_env ]; then
  # shellcheck disable=SC1091
  . /etc/ssh/sshd_env
  log "loaded /etc/ssh/sshd_env"
fi

log "env POC_LOG_LEVEL=${POC_LOG_LEVEL:-<unset>} DATA_DIR=${DATA_DIR:-<unset>} DB_HOST=${DB_HOST:-<unset>} PWD=${PWD:-<unset>}"

# Ensure /srv is on the module path regardless of cwd.
export PYTHONPATH="/srv:${PYTHONPATH:-}"

exec /usr/local/bin/python /srv/app/poc_gateway.py "$@"
