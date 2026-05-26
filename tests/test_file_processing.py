from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.exc import SQLAlchemyError

from app.ingestion import file_handler


def make_settings(tmp_path):
    incoming_dir = tmp_path / 'incoming'
    processing_dir = tmp_path / 'processing'
    processed_dir = tmp_path / 'processed'
    failed_dir = tmp_path / 'failed'

    incoming_dir.mkdir()
    processing_dir.mkdir()
    processed_dir.mkdir()
    failed_dir.mkdir()

    return SimpleNamespace(
        incoming_dir=incoming_dir,
        processing_dir=processing_dir,
        processed_dir=processed_dir,
        failed_dir=failed_dir,
    )


def test_process_rolls_back_and_marks_failure_on_db_error(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    incoming_file = settings.incoming_dir / 'customers.csv'
    incoming_file.write_text('a,b\n1,2\n', encoding='utf-8')

    class FakeSession:
        def __init__(self):
            self.rollback_called = False
            self.closed = False

        def rollback(self):
            self.rollback_called = True

        def close(self):
            self.closed = True

    class FakeLoader:
        failure_updates = []

        def __init__(self, db):
            self.db = db

        def create_source_file(self, file_path: Path, status: str = 'processing'):
            return SimpleNamespace(id='file-1')

        def create_pipeline_run(self, file_id):
            return SimpleNamespace(id='run-1')

        def store_valid_rows(self, file_id, valid_rows):
            raise SQLAlchemyError('write failed')

        def store_invalid_rows(self, file_id, invalid_rows):
            raise AssertionError('invalid rows should not be stored after a DB write failure')

        def finalize_pipeline_run_by_id(
            self,
            run_id,
            rows_total,
            rows_valid,
            rows_failed,
            status,
            error_message=None,
        ):
            self.failure_updates.append(
                ('run', run_id, rows_total, rows_valid, rows_failed, status, error_message)
            )

        def update_source_file_status_by_id(self, source_file_id, status):
            self.failure_updates.append(('file', source_file_id, status))

    main_session = FakeSession()
    cleanup_session = FakeSession()
    sessions = [main_session, cleanup_session]

    def fake_session_local():
        return sessions.pop(0)

    monkeypatch.setattr(file_handler, 'get_settings', lambda: settings)
    monkeypatch.setattr(file_handler, 'SessionLocal', fake_session_local)
    monkeypatch.setattr(file_handler, 'DBLoader', FakeLoader)
    monkeypatch.setattr(
        file_handler,
        'parse_tabular_file',
        lambda path: [{'row_number': 1, 'row_data': {'name': 'Ada'}}],
    )
    monkeypatch.setattr(
        file_handler.FileProcessor,
        '_wait_for_file_ready',
        staticmethod(lambda path, max_attempts=10, delay_seconds=0.25: None),
    )

    result = file_handler.FileProcessor().process(incoming_file)

    assert result.success is False
    assert result.rows_total == 1
    assert result.rows_valid == 1
    assert result.rows_failed == 0
    assert result.final_path == settings.failed_dir / 'customers.csv'
    assert result.final_path.exists()
    assert main_session.rollback_called is True
    assert main_session.closed is True
    assert cleanup_session.closed is True
    assert sessions == []
    assert FakeLoader.failure_updates == [
        ('run', 'run-1', 1, 1, 0, 'failed', 'write failed'),
        ('file', 'file-1', 'failed'),
    ]
