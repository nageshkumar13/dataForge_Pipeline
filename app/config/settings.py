from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseSettings, Field


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / '.env')


class Settings(BaseSettings):
    database_url: str = Field(..., env='DATABASE_URL')
    pipeline_scan_interval: int = Field(5, env='PIPELINE_SCAN_INTERVAL')

    incoming_dir: Path = ROOT_DIR / 'storage' / 'incoming'
    processing_dir: Path = ROOT_DIR / 'storage' / 'processing'
    processed_dir: Path = ROOT_DIR / 'storage' / 'processed'
    failed_dir: Path = ROOT_DIR / 'storage' / 'failed'
    logs_dir: Path = ROOT_DIR / 'logs'

    class Config:
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
