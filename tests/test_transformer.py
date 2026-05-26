from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd

from app.transform.transformer import Transformer


def test_transformer_sanitizes_json_unsafe_values():
    records = [
        {
            'row_number': 1,
            'row_data': {
                'created_at': datetime(2024, 1, 2, 3, 4, 5),
                'ship_date': date(2024, 1, 3),
                'ship_time': time(9, 30, 0),
                'duration': timedelta(minutes=15),
                'price': Decimal('19.95'),
                'path': Path('storage/incoming/sample.csv'),
                'optional': pd.NA,
                'missing_time': pd.NaT,
                'nested': {
                    'values': [Decimal('2.5'), float('nan')],
                },
            },
        }
    ]

    transformed = Transformer().transform(records)
    row = transformed[0]['row_data']

    assert row['created_at'] == '2024-01-02T03:04:05'
    assert row['ship_date'] == '2024-01-03'
    assert row['ship_time'] == '09:30:00'
    assert row['duration'] == 900.0
    assert row['price'] == 19.95
    assert row['path'] == 'storage/incoming/sample.csv'
    assert row['optional'] is None
    assert row['missing_time'] is None
    assert row['nested'] == {'values': [2.5, None]}
