from typing import Any

import pandas as pd


ValidationResult = dict[str, list[dict[str, Any]]]


class Validator:
    def validate_rows(self, records: list[dict[str, Any]]) -> ValidationResult:
        valid: list[dict[str, Any]] = []
        invalid: list[dict[str, Any]] = []

        for record in records:
            row_number = int(record['row_number'])
            row_data = record['row_data']

            if not isinstance(row_data, dict) or len(row_data) == 0:
                invalid.append(
                    {
                        'row_number': row_number,
                        'error_type': 'EMPTY_ROW',
                        'error_message': 'Row has no columns.',
                        'failed_data': row_data if isinstance(row_data, dict) else {},
                    }
                )
                continue

            if all(self._is_effectively_empty(value) for value in row_data.values()):
                invalid.append(
                    {
                        'row_number': row_number,
                        'error_type': 'EMPTY_ROW',
                        'error_message': 'Row contains only empty values.',
                        'failed_data': row_data,
                    }
                )
                continue

            null_columns = [col for col, val in row_data.items() if self._is_effectively_empty(val)]
            if null_columns:
                valid.append(
                    {
                        'row_number': row_number,
                        'row_data': row_data,
                        'warnings': [f'Null-like values in columns: {", ".join(null_columns)}'],
                    }
                )
            else:
                valid.append({'row_number': row_number, 'row_data': row_data, 'warnings': []})

        return {'valid': valid, 'invalid': invalid}

    @staticmethod
    def _is_effectively_empty(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == '':
            return True
        try:
            return bool(pd.isna(value))
        except Exception:
            return False
