from types import SimpleNamespace

import pytest

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


def test_reprocess_file_raises_when_processing_fails(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    (settings.failed_dir / 'broken.csv').write_text('a,b\n1,2\n', encoding='utf-8')

    class StubProcessor:
        def process(self, path):
            return file_handler.ProcessingResult(
                file_name=path.name,
                success=False,
                error_message='still broken',
            )

    monkeypatch.setattr(file_handler, 'get_settings', lambda: settings)
    monkeypatch.setattr(file_handler, 'FileProcessor', StubProcessor)

    with pytest.raises(file_handler.ReprocessFailedError, match='still broken'):
        file_handler.reprocess_file('broken.csv')


def test_reprocess_all_failed_counts_only_successes(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    (settings.failed_dir / 'good.csv').write_text('a,b\n1,2\n', encoding='utf-8')
    (settings.failed_dir / 'bad.xlsx').write_text('placeholder', encoding='utf-8')
    (settings.failed_dir / 'ignore.txt').write_text('nope', encoding='utf-8')

    class StubProcessor:
        def process(self, path):
            return file_handler.ProcessingResult(
                file_name=path.name,
                success=path.name == 'good.csv',
                error_message=None if path.name == 'good.csv' else 'failed again',
            )

    monkeypatch.setattr(file_handler, 'get_settings', lambda: settings)
    monkeypatch.setattr(file_handler, 'FileProcessor', StubProcessor)

    summary = file_handler.reprocess_all_failed()

    assert summary.attempted_count == 2
    assert summary.reprocessed_count == 1
    assert summary.failed_count == 1
    assert summary.failed_files == ['bad.xlsx']
    assert (settings.failed_dir / 'ignore.txt').exists()
