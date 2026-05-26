from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import PipelineRun, SourceFile, ValidationError
from app.ingestion.file_handler import (
    ReprocessFailedError,
    reprocess_all_failed,
    reprocess_file,
)


router = APIRouter()


class ReprocessRequest(BaseModel):
    file_name: str | None = None


@router.get('/health')
def health() -> dict:
    return {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()}


@router.get('/pipeline/runs')
def get_pipeline_runs(db: Session = Depends(get_db)) -> list[dict]:
    runs = db.execute(select(PipelineRun).order_by(PipelineRun.start_time.desc())).scalars().all()
    return [
        {
            'id': str(run.id),
            'file_id': str(run.file_id),
            'start_time': run.start_time,
            'end_time': run.end_time,
            'rows_total': run.rows_total,
            'rows_valid': run.rows_valid,
            'rows_failed': run.rows_failed,
            'status': run.status,
            'error_message': run.error_message,
        }
        for run in runs
    ]


@router.get('/files')
def get_files(db: Session = Depends(get_db)) -> list[dict]:
    files = db.execute(select(SourceFile).order_by(SourceFile.uploaded_at.desc())).scalars().all()
    return [
        {
            'id': str(item.id),
            'file_name': item.file_name,
            'file_type': item.file_type,
            'file_size_bytes': item.file_size_bytes,
            'source_path': item.source_path,
            'checksum': item.checksum,
            'status': item.status,
            'uploaded_at': item.uploaded_at,
            'processed_at': item.processed_at,
        }
        for item in files
    ]


@router.get('/errors')
def get_errors(db: Session = Depends(get_db), limit: int = 100) -> list[dict]:
    errors = db.execute(
        select(ValidationError).order_by(ValidationError.created_at.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            'id': item.id,
            'file_id': str(item.file_id),
            'row_number': item.row_number,
            'error_type': item.error_type,
            'error_message': item.error_message,
            'failed_data': item.failed_data,
            'created_at': item.created_at,
        }
        for item in errors
    ]


@router.post('/pipeline/reprocess')
def reprocess(payload: ReprocessRequest) -> dict:
    if payload.file_name:
        try:
            file_name = reprocess_file(payload.file_name)
            return {'status': 'success', 'file_name': file_name}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ReprocessFailedError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    summary = reprocess_all_failed()
    status = 'success' if summary.failed_count == 0 else 'partial_success'
    return {
        'status': status,
        'attempted_count': summary.attempted_count,
        'reprocessed_count': summary.reprocessed_count,
        'failed_count': summary.failed_count,
        'failed_files': summary.failed_files,
    }
