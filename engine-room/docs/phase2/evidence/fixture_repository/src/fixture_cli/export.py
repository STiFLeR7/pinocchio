import json

def export_json(data, path):
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle)
