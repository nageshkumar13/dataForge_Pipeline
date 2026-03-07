import shutil
import time
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


class FileProcessor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.validator = Validator()
        self.transformer = Transformer()

    def process(self, file_path: Path) -> None:
        start = time.perf_counter()
        if not file_path.exists():
            logger.warning(f'File no longer exists: {file_path}')
            return

        processing_path = self.settings.processing_dir / file_path.name
        shutil.move(str(file_path), processing_path)
        logger.info(f'file detected | moved to processing | file={processing_path.name}')

        db = SessionLocal()
        loader = DBLoader(db)
        source_file = None
        run = None

        try:
            source_file = loader.create_source_file(processing_path, status='processing')
            run = loader.create_pipeline_run(source_file.id)

            records = parse_tabular_file(processing_path)
            transformed = self.transformer.transform(records)
            validation_result = self.validator.validate_rows(transformed)

            valid_rows = validation_result['valid']
            invalid_rows = validation_result['invalid']

            loader.store_valid_rows(source_file.id, valid_rows)
            loader.store_invalid_rows(source_file.id, invalid_rows)

            warning_count = sum(1 for row in valid_rows if row.get('warnings'))
            if warning_count > 0:
                logger.info(f'null values found | file={processing_path.name} | rows_with_nulls={warning_count}')

            loader.finalize_pipeline_run(
                run=run,
                rows_total=len(transformed),
                rows_valid=len(valid_rows),
                rows_failed=len(invalid_rows),
                status='completed',
            )
            loader.update_source_file_status(source_file, 'processed')

            destination = self.settings.processed_dir / processing_path.name
            shutil.move(str(processing_path), destination)

            elapsed = time.perf_counter() - start
            logger.info(
                f'rows processed | file={destination.name} | total={len(transformed)} | valid={len(valid_rows)} | '
                f'failed={len(invalid_rows)} | seconds={elapsed:.3f}'
            )
        except (ParserError, SQLAlchemyError, Exception) as exc:  # noqa: BLE001
            logger.exception(f'pipeline error | file={processing_path.name} | error={exc}')
            if run is not None:
                loader.finalize_pipeline_run(
                    run=run,
                    rows_total=run.rows_total,
                    rows_valid=run.rows_valid,
                    rows_failed=run.rows_failed,
                    status='failed',
                    error_message=str(exc),
                )
            if source_file is not None:
                loader.update_source_file_status(source_file, 'failed')

            failed_path = self.settings.failed_dir / processing_path.name
            if processing_path.exists():
                shutil.move(str(processing_path), failed_path)
        finally:
            db.close()


def reprocess_file(file_name: str) -> str:
    settings = get_settings()
    failed_path = settings.failed_dir / file_name

    if not failed_path.exists():
        raise FileNotFoundError(f'File not found in failed folder: {file_name}')

    incoming_path = settings.incoming_dir / file_name
    failed_path.replace(incoming_path)

    processor = FileProcessor()
    processor.process(incoming_path)
    return file_name


def reprocess_all_failed() -> int:
    settings = get_settings()
    processor = FileProcessor()
    count = 0

    for path in settings.failed_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in {'.csv', '.xlsx'}:
            continue
        target = settings.incoming_dir / path.name
        path.replace(target)
        processor.process(target)
        count += 1

    logger.info(f'reprocessed files | count={count}')
    return count
