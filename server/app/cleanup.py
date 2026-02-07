from app.db import init_db
from app.cleanup_worker import CleanupConfig, run_cleanup_loop


def main() -> None:
    init_db()
    config = CleanupConfig.from_env()
    run_cleanup_loop(config)


if __name__ == "__main__":
    main()
