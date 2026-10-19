def load_config(path):
    with open(path, encoding='utf-8') as handle:
        return dict(line.split('=', 1) for line in handle if '=' in line)
