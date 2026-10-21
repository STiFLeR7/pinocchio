from fixture_cli.main import main

def test_run_command():
    assert main(['run']).command == 'run'

def test_status_command():
    assert main(['status']).command == 'status'
