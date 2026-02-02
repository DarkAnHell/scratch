#!/usr/bin/env sh
set -eu

user="${1:-}"
key_type="${2:-}"
key_b64="${3:-}"

keys_dir="${KEYS_DIR:-/keys}"

if [ -f /etc/ssh/sshd_env ]; then
  # shellcheck disable=SC1091
  . /etc/ssh/sshd_env
fi

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
    echo "${level} ${ts} AUTH_KEYS $*" >>"${LOG_SINK}"
  fi
}

log_error() { log ERROR "$*"; }
log_warn() { log WARNING "$*"; }
log_info() { log INFO "$*"; }
log_debug() { log DEBUG "$*"; }
log_verbose() { log VERBOSE "$*"; }

user_keys_file() {
  echo "/home/$1/.ssh/authorized_keys"
}

emit_file_if_present() {
  f="$1"
  if [ -f "$f" ] && [ -s "$f" ]; then
    cat "$f"
    return 0
  fi
  return 1
}

seed_from_pub_if_present() {
  pub="$1"
  dest="$2"
  if [ -f "$pub" ] && [ -s "$pub" ]; then
    install -m 600 "$pub" "$dest"
    cat "$dest"
    return 0
  fi
  return 1
}

clean_token() {
  # If sshd didn't expand a token, it will be passed literally like "%k".
  if [ "$1" = "%k" ] || [ "$1" = "%t" ]; then
    echo ""
  else
    echo "$1"
  fi
}

key_type="$(clean_token "$key_type")"
key_b64="$(clean_token "$key_b64")"

log_info "invoked user=${user} key_type=${key_type:-<empty>} key_b64_len=${#key_b64}"

# Always accept the presented key for put/get (no signup required).
if [ "$user" = "put" ] || [ "$user" = "get" ]; then
  if [ -n "$key_type" ] && [ -n "$key_b64" ]; then
    log_debug "accepting presented key for user=${user}"
    printf "%s %s\n" "$key_type" "$key_b64"
    exit 0
  fi
  log_warn "no key presented for user=${user}"
fi

# No fallback to pre-provided keys.
log_info "no key emitted for user=${user}"
exit 0
