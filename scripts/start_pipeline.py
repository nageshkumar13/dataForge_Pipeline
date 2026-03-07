from app.ingestion.file_watcher import FileWatcher
from app.logging.logger import get_logger


def main() -> None:
    logger = get_logger()
    logger.info('starting dataforge pipeline')
    watcher = FileWatcher()
    watcher.start()


if __name__ == '__main__':
    main()
