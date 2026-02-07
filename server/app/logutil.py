from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Final

_LEVELS: Final[dict[str, int]] = {
    "ERROR": 0,
    "WARNING": 1,
    "INFO": 2,
    "DEBUG": 3,
    "VERBOSE": 4,
}
_ALIASES: Final[dict[str, str]] = {
    "WARN": "WARNING",
    "ERR": "ERROR",
    "TRACE": "VERBOSE",
}
_DEFAULT_LEVEL: Final[str] = "INFO"
_CURRENT_LEVEL: int | None = None
_LEVEL_SOURCE: str | None = None


def _sink_path() -> str | None:
    raw = os.environ.get("LOG_SINK")
    if not raw:
        return None
    name = raw.strip()
    if not name or name.lower() in ("stderr", "sys.stderr"):
        return None
    return name


def _resolve_level_name(raw: str | None) -> str:
    if not raw:
        return _DEFAULT_LEVEL
    name = raw.strip().upper()
    name = _ALIASES.get(name, name)
    if name in _LEVELS:
        return name
    return _DEFAULT_LEVEL


def _load_level() -> None:
    global _CURRENT_LEVEL, _LEVEL_SOURCE
    raw = os.environ.get("LOG_LEVEL")
    source = "LOG_LEVEL"
    name = _resolve_level_name(raw)
    _CURRENT_LEVEL = _LEVELS[name]
    _LEVEL_SOURCE = source
    if raw is not None:
        raw_name = raw.strip().upper()
        if raw_name not in _LEVELS and raw_name not in _ALIASES:
            _emit(
                "WARNING",
                f"unknown log level {raw!r} from {_LEVEL_SOURCE}, defaulting to {_DEFAULT_LEVEL}",
            )


def _level() -> int:
    if _CURRENT_LEVEL is None:
        _load_level()
    return _CURRENT_LEVEL


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(level: str, msg: str) -> None:
    line = f"{level} {_ts()} {msg}\n"
    sink = _sink_path()
    if sink:
        try:
            with open(sink, "a", encoding="utf-8") as f:
                f.write(line)
            return
        except Exception:
            pass
    sys.stderr.write(line)
    sys.stderr.flush()


def log(level: str, msg: str) -> None:
    level_name = _resolve_level_name(level)
    if _LEVELS[level_name] <= _level():
        _emit(level_name, msg)


def error(msg: str) -> None:
    log("ERROR", msg)


def warning(msg: str) -> None:
    log("WARNING", msg)


def info(msg: str) -> None:
    log("INFO", msg)


def debug(msg: str) -> None:
    log("DEBUG", msg)


def verbose(msg: str) -> None:
    log("VERBOSE", msg)
