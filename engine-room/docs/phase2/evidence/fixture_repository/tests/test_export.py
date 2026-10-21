import json
from fixture_cli.export import export_json

def test_export_json(tmp_path):
    path = tmp_path / 'data.json'
    export_json({'ok': True}, path)
    assert json.loads(path.read_text(encoding='utf-8')) == {'ok': True}
