from app.ingestion.parser import parse_tabular_file


def test_parser_empty_support(tmp_path):
    sample = tmp_path / 'sample.csv'
    sample.write_text('a,b\n1,2\n', encoding='utf-8')
    records = parse_tabular_file(sample)
    assert len(records) == 1
    assert records[0]['row_data']['a'] == 1
