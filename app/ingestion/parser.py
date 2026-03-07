from collections.abc import Iterable
from pathlib import Path

import pandas as pd


SUPPORTED_EXTENSIONS = {'.csv', '.xlsx'}


class ParserError(Exception):
    pass


def parse_tabular_file(file_path: Path) -> list[dict]:
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ParserError(f'Unsupported extension: {ext}')

    if ext == '.csv':
        frame = pd.read_csv(file_path)
    else:
        frame = pd.read_excel(file_path)

    return frame_to_records(frame)


def frame_to_records(frame: pd.DataFrame) -> list[dict]:
    if frame.empty and len(frame.columns) == 0:
        return []

    frame.columns = [str(col) for col in frame.columns]
    return [
        {
            'row_number': int(index) + 1,
            'row_data': {str(k): v for k, v in row.to_dict().items()},
        }
        for index, (_, row) in enumerate(frame.iterrows())
    ]
