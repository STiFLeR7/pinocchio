import argparse

def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('run')
    sub.add_parser('status')
    return parser.parse_args(argv)
