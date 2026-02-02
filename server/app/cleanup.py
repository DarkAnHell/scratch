import os
import time
from pathlib import Path
from app.db import delete_expired, utcnow, init_db

def main() -> None:
    init_db()
    data_dir = Path(os.environ.get("DATA_DIR", "/data")).resolve()
    interval = int(os.environ.get("CLEAN_INTERVAL_SECONDS", "60"))

    while True:
        now = utcnow()
        expired = delete_expired(now)
        for token, stored_path in expired:
            try:
                p = Path(stored_path)
                if p.exists() and p.is_file():
                    p.unlink()
            except Exception:
                pass
        time.sleep(interval)

if __name__ == "__main__":
    main()