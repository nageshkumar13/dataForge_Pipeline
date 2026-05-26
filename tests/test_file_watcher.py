from pathlib import Path
from types import SimpleNamespace

from app.ingestion.file_watcher import IncomingFileEventHandler


def test_event_handler_processes_supported_moved_files():
    calls = []

    class FakeProcessor:
        def process(self, path: Path):
            calls.append(path)

    handler = IncomingFileEventHandler(FakeProcessor())
    event = SimpleNamespace(is_directory=False, dest_path='storage/incoming/upload.csv')

    handler.on_moved(event)

    assert calls == [Path('storage/incoming/upload.csv')]
