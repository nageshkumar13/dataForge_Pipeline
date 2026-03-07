from typing import Any


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

    @staticmethod
    def _sanitize_value(value: Any) -> Any:
        if hasattr(value, 'item'):
            return value.item()
        return value
