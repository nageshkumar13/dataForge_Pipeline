from app.ingestion.file_handler import reprocess_all_failed
from app.logging.logger import get_logger


if __name__ == '__main__':
    logger = get_logger()
    summary = reprocess_all_failed()
    logger.info(
        f'reprocess complete | attempted={summary.attempted_count} | '
        f'succeeded={summary.reprocessed_count} | failed={summary.failed_count}'
    )
