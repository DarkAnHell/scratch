#!/usr/bin/env bash
set -euo pipefail

: "${KEYS_DIR:=/keys}"
: "${SERVICE:=sshgateway}"
: "${LOG_LEVEL:=INFO}"

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

log_info "creating test keys in docker volume 'ssh_keys' via service ${SERVICE}"

docker compose run --rm --no-deps \
  -e KEYS_DIR="${KEYS_DIR}" \
  -e LOG_LEVEL="${LOG_LEVEL}" \
  --entrypoint /bin/sh \
  "${SERVICE}" \
  -c 'set -euo pipefail
mkdir -p "$KEYS_DIR"
umask 077
generate_key() {
  name="$1"
  if [ ! -f "$KEYS_DIR/$name" ]; then
    ssh-keygen -t ed25519 -N "" -f "$KEYS_DIR/$name" >/dev/null
  fi
}
generate_key "put"
generate_key "get"
chmod 600 "$KEYS_DIR/put" "$KEYS_DIR/get"
chmod 644 "$KEYS_DIR/put.pub" "$KEYS_DIR/get.pub"
echo "Keys ready: $KEYS_DIR/put(.pub), $KEYS_DIR/get(.pub)"
'
