import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.config.settings import get_settings
from app.database.connection import SessionLocal
from app.ingestion.parser import ParserError, parse_tabular_file
from app.load.db_loader import DBLoader
from app.logging.logger import get_logger
from app.transform.transformer import Transformer
from app.validation.validator import Validator


logger = get_logger()


@dataclass(slots=True)
class ProcessingResult:
    file_name: str
    success: bool
    rows_total: int = 0
    rows_valid: int = 0
    rows_failed: int = 0
    error_message: str | None = None
    final_path: Path | None = None


@dataclass(slots=True)
class ReprocessSummary:
    attempted_count: int
    reprocessed_count: int
    failed_files: list[str] = field(default_factory=list)

    @property
    def failed_count(self) -> int:
        return len(self.failed_files)


class ReprocessFailedError(RuntimeError):
    pass


class FileProcessor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.validator = Validator()
        self.transformer = Transformer()

    def process(self, file_path: Path) -> ProcessingResult:
        start = time.perf_counter()
        if not file_path.exists():
            logger.warning(f'File no longer exists: {file_path}')
            return ProcessingResult(
                file_name=file_path.name,
                success=False,
                error_message='File no longer exists.',
            )

        processing_path = self.settings.processing_dir / file_path.name
        db = None
        source_file = None
        run = None
        rows_total = 0
        rows_valid = 0
        rows_failed = 0

        try:
            self._wait_for_file_ready(file_path)
            shutil.move(str(file_path), processing_path)
            logger.info(f'file detected | moved to processing | file={processing_path.name}')

            db = SessionLocal()
            loader = DBLoader(db)
            source_file = loader.create_source_file(processing_path, status='processing')
            run = loader.create_pipeline_run(source_file.id)

            records = parse_tabular_file(processing_path)
            transformed = self.transformer.transform(records)
            validation_result = self.validator.validate_rows(transformed)

            valid_rows = validation_result['valid']
            invalid_rows = validation_result['invalid']
            rows_total = len(transformed)
            rows_valid = len(valid_rows)
            rows_failed = len(invalid_rows)

            loader.store_valid_rows(source_file.id, valid_rows)
            loader.store_invalid_rows(source_file.id, invalid_rows)

            warning_count = sum(1 for row in valid_rows if row.get('warnings'))
            if warning_count > 0:
                logger.info(f'null values found | file={processing_path.name} | rows_with_nulls={warning_count}')

            loader.finalize_pipeline_run(
                run=run,
                rows_total=rows_total,
                rows_valid=rows_valid,
                rows_failed=rows_failed,
                status='completed',
            )
            loader.update_source_file_status(source_file, 'processed')

            destination = self.settings.processed_dir / processing_path.name
            shutil.move(str(processing_path), destination)

            elapsed = time.perf_counter() - start
            logger.info(
                f'rows processed | file={destination.name} | total={rows_total} | valid={rows_valid} | '
                f'failed={rows_failed} | seconds={elapsed:.3f}'
            )
            return ProcessingResult(
                file_name=destination.name,
                success=True,
                rows_total=rows_total,
                rows_valid=rows_valid,
                rows_failed=rows_failed,
                final_path=destination,
            )
        except (ParserError, SQLAlchemyError, Exception) as exc:  # noqa: BLE001
            logger.exception(f'pipeline error | file={processing_path.name} | error={exc}')
            if db is not None:
                self._rollback_session(db)

            self._mark_failure(
                run_id=getattr(run, 'id', None),
                source_file_id=getattr(source_file, 'id', None),
                rows_total=rows_total,
                rows_valid=rows_valid,
                rows_failed=rows_failed,
                error_message=str(exc),
            )

            failed_path = self.settings.failed_dir / processing_path.name
            self._move_to_failed(processing_path, failed_path)
            return ProcessingResult(
                file_name=file_path.name,
                success=False,
                rows_total=rows_total,
                rows_valid=rows_valid,
                rows_failed=rows_failed,
                error_message=str(exc),
                final_path=failed_path if failed_path.exists() else None,
            )
        finally:
            if db is not None:
                db.close()

    @staticmethod
    def _rollback_session(db) -> None:
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            logger.exception('failed to rollback session after pipeline error')

    def _mark_failure(
        self,
        run_id,
        source_file_id,
        rows_total: int,
        rows_valid: int,
        rows_failed: int,
        error_message: str,
    ) -> None:
        if run_id is None and source_file_id is None:
            return

        cleanup_db = SessionLocal()
        cleanup_loader = DBLoader(cleanup_db)
        try:
            if run_id is not None:
                cleanup_loader.finalize_pipeline_run_by_id(
                    run_id=run_id,
                    rows_total=rows_total,
                    rows_valid=rows_valid,
                    rows_failed=rows_failed,
                    status='failed',
                    error_message=error_message,
                )
            if source_file_id is not None:
                cleanup_loader.update_source_file_status_by_id(source_file_id, 'failed')
        except Exception:  # noqa: BLE001
            logger.exception('failed to persist pipeline failure state')
        finally:
            cleanup_db.close()

    @staticmethod
    def _move_to_failed(processing_path: Path, failed_path: Path) -> None:
        if not processing_path.exists():
            return
        try:
            shutil.move(str(processing_path), failed_path)
        except Exception:  # noqa: BLE001
            logger.exception(f'failed to move file to failed directory | file={processing_path.name}')

    @staticmethod
    def _wait_for_file_ready(file_path: Path, max_attempts: int = 10, delay_seconds: float = 0.25) -> None:
        last_size = None
        for _ in range(max_attempts):
            if not file_path.exists():
                raise FileNotFoundError(f'File no longer exists: {file_path}')

            current_size = file_path.stat().st_size
            if current_size == last_size:
                with file_path.open('rb'):
                    return

            last_size = current_size
            time.sleep(delay_seconds)

        raise TimeoutError(f'File did not stabilize before processing: {file_path.name}')


def reprocess_file(file_name: str) -> str:
    settings = get_settings()
    failed_path = settings.failed_dir / file_name

    if not failed_path.exists():
        raise FileNotFoundError(f'File not found in failed folder: {file_name}')

    incoming_path = settings.incoming_dir / file_name
    failed_path.replace(incoming_path)

    processor = FileProcessor()
    result = processor.process(incoming_path)
    if not result.success:
        raise ReprocessFailedError(result.error_message or f'Failed to reprocess file: {file_name}')
    return file_name


def reprocess_all_failed() -> ReprocessSummary:
    settings = get_settings()
    processor = FileProcessor()
    attempted_count = 0
    reprocessed_count = 0
    failed_files: list[str] = []

    for path in settings.failed_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in {'.csv', '.xlsx'}:
            continue

        attempted_count += 1
        target = settings.incoming_dir / path.name
        path.replace(target)
        result = processor.process(target)
        if result.success:
            reprocessed_count += 1
        else:
            failed_files.append(path.name)

    summary = ReprocessSummary(
        attempted_count=attempted_count,
        reprocessed_count=reprocessed_count,
        failed_files=failed_files,
    )
    logger.info(
        f'reprocessed files | attempted={summary.attempted_count} | '
        f'succeeded={summary.reprocessed_count} | failed={summary.failed_count}'
    )
    return summary
