from fixture_cli.config import load_config

def test_load_config(tmp_path):
    path = tmp_path / 'config.ini'
    path.write_text('mode=fast', encoding='utf-8')
    assert load_config(path) == {'mode': 'fast'}
