import os
import time
from pathlib import Path
from app.db import delete_expired, utcnow, init_db
from app import logutil


def main() -> None:
    init_db()
    data_dir = Path(os.environ.get("DATA_DIR", "/data")).resolve()
    interval = int(os.environ.get("CLEAN_INTERVAL_SECONDS", "60"))
    logutil.info(f"cleanup: starting data_dir={data_dir} interval_seconds={interval}")

    while True:
        now = utcnow()
        expired = delete_expired(now)
        if not expired:
            logutil.debug("cleanup: no expired files")
        for token, stored_path in expired:
            try:
                p = Path(stored_path)
                if p.exists() and p.is_file():
                    p.unlink()
                    logutil.verbose(
                        f"cleanup: removed token={token} path={stored_path}"
                    )
                else:
                    logutil.warning(
                        f"cleanup: missing file token={token} path={stored_path}"
                    )
            except Exception as e:
                logutil.error(
                    f"cleanup: failed to remove token={token} path={stored_path} err={e!r}"
                )
        time.sleep(interval)


if __name__ == "__main__":
    main()
