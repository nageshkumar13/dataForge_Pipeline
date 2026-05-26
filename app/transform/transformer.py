from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd


class Transformer:
    def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        transformed: list[dict[str, Any]] = []
        for item in records:
            row_data = {
                str(key).strip(): self._sanitize_value(value)
                for key, value in item['row_data'].items()
            }
            transformed.append({'row_number': int(item['row_number']), 'row_data': row_data})
        return transformed

    def _sanitize_value(self, value: Any) -> Any:
        if hasattr(value, 'item'):
            try:
                value = value.item()
            except Exception:  # noqa: BLE001
                pass

        if self._is_null_like(value):
            return None

        if isinstance(value, dict):
            return {str(key): self._sanitize_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._sanitize_value(item) for item in value]
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, timedelta):
            return value.total_seconds()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, Path):
            return str(value)

        return value

    @staticmethod
    def _is_null_like(value: Any) -> bool:
        if value is None:
            return True
        try:
            return bool(pd.isna(value))
        except Exception:  # noqa: BLE001
            return False
