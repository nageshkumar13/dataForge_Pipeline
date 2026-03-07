import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.config.settings import get_settings
from app.ingestion.file_handler import FileProcessor
from app.logging.logger import get_logger


logger = get_logger()


class IncomingFileEventHandler(FileSystemEventHandler):
    def __init__(self, processor: FileProcessor) -> None:
        self.processor = processor
        self.supported = {'.csv', '.xlsx'}

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() in self.supported:
            self.processor.process(path)


class FileWatcher:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.processor = FileProcessor()
        self.observer = Observer()

    def _process_existing_files(self) -> None:
        for path in self.settings.incoming_dir.iterdir():
            if path.is_file() and path.suffix.lower() in {'.csv', '.xlsx'}:
                self.processor.process(path)

    def start(self) -> None:
        self.settings.incoming_dir.mkdir(parents=True, exist_ok=True)
        self.settings.processing_dir.mkdir(parents=True, exist_ok=True)
        self.settings.processed_dir.mkdir(parents=True, exist_ok=True)
        self.settings.failed_dir.mkdir(parents=True, exist_ok=True)

        self._process_existing_files()

        handler = IncomingFileEventHandler(self.processor)
        self.observer.schedule(handler, str(self.settings.incoming_dir), recursive=False)
        self.observer.start()
        logger.info('watcher started | monitoring storage/incoming')

        try:
            while True:
                time.sleep(self.settings.pipeline_scan_interval)
        except KeyboardInterrupt:
            logger.info('watcher stopping')
            self.observer.stop()
        finally:
            self.observer.join()
