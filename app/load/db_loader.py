import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.database.models import PipelineRun, RawRecord, SourceFile, ValidationError


def checksum_for_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8192), b''):
            digest.update(chunk)
    return digest.hexdigest()


class DBLoader:
    def __init__(self, db: Session):
        self.db = db

    def create_source_file(self, file_path: Path, status: str = 'processing') -> SourceFile:
        source_file = SourceFile(
            file_name=file_path.name,
            file_type=file_path.suffix.lower().replace('.', ''),
            file_size_bytes=file_path.stat().st_size,
            source_path=str(file_path),
            checksum=checksum_for_file(file_path),
            status=status,
        )
        self.db.add(source_file)
        self.db.commit()
        self.db.refresh(source_file)
        return source_file

    def create_pipeline_run(self, file_id) -> PipelineRun:
        run = PipelineRun(file_id=file_id, start_time=datetime.utcnow(), status='running')
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def store_valid_rows(self, file_id, valid_rows: list[dict[str, Any]]) -> None:
        if not valid_rows:
            return
        self.db.add_all(
            [
                RawRecord(
                    file_id=file_id,
                    row_number=int(item['row_number']),
                    row_data=item['row_data'],
                )
                for item in valid_rows
            ]
        )
        self.db.commit()

    def store_invalid_rows(self, file_id, invalid_rows: list[dict[str, Any]]) -> None:
        if not invalid_rows:
            return
        self.db.add_all(
            [
                ValidationError(
                    file_id=file_id,
                    row_number=int(item['row_number']),
                    error_type=item['error_type'],
                    error_message=item['error_message'],
                    failed_data=item.get('failed_data', {}),
                )
                for item in invalid_rows
            ]
        )
        self.db.commit()

    def finalize_pipeline_run(
        self,
        run: PipelineRun,
        rows_total: int,
        rows_valid: int,
        rows_failed: int,
        status: str,
        error_message: str | None = None,
    ) -> PipelineRun:
        run.rows_total = rows_total
        run.rows_valid = rows_valid
        run.rows_failed = rows_failed
        run.status = status
        run.error_message = error_message
        run.end_time = datetime.utcnow()
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def update_source_file_status(self, source_file: SourceFile, status: str) -> SourceFile:
        source_file.status = status
        source_file.processed_at = datetime.utcnow()
        self.db.add(source_file)
        self.db.commit()
        self.db.refresh(source_file)
        return source_file
