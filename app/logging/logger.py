from pathlib import Path

from loguru import logger

from app.config.settings import get_settings


_configured = False


def get_logger():
    global _configured
    if _configured:
        return logger

    settings = get_settings()
    Path(settings.logs_dir).mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        settings.logs_dir / 'pipeline.log',
        level='INFO',
        rotation='10 MB',
        retention='10 days',
        enqueue=True,
        backtrace=True,
        diagnose=False,
        format='{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}',
    )
    logger.add(lambda msg: print(msg, end=''), level='INFO')
    _configured = True
    return logger
