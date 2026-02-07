from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Callable

from app import logutil
from app.db import delete_expired, utcnow


@dataclass(frozen=True)
class CleanupConfig:
    data_dir: Path
    interval_seconds: int

    @classmethod
    def from_env(cls) -> "CleanupConfig":
        # Resolve configuration once at startup for stable logging.
        data_dir = Path(os.environ.get("DATA_DIR", "/data")).resolve()
        interval = int(os.environ.get("CLEAN_INTERVAL_SECONDS", "60"))
        return cls(data_dir=data_dir, interval_seconds=interval)


def remove_expired_files(expired: Iterable[tuple[str, str]]) -> None:
    # Remove files already deleted from DB.
    for token, stored_path in expired:
        try:
            path = Path(stored_path)
            if path.is_file():
                path.unlink()
                logutil.verbose(
                    f"cleanup: removed token={token} path={stored_path}"
                )
            else:
                logutil.warning(
                    f"cleanup: missing file token={token} path={stored_path}"
                )
        except Exception as exc:
            logutil.error(
                f"cleanup: failed to remove token={token} path={stored_path} err={exc!r}"
            )


def run_cleanup_loop(
    config: CleanupConfig, *, sleep: Callable[[float], None] = time.sleep
) -> None:
    logutil.info(
        f"cleanup: starting data_dir={config.data_dir} interval_seconds={config.interval_seconds}"
    )
    while True:
        expired = delete_expired(utcnow())
        if not expired:
            logutil.debug("cleanup: no expired files")
        remove_expired_files(expired)
        logutil.debug("cleanup: sleeping")
        sleep(config.interval_seconds)
