"""Standalone script: python -m src.tools.cli.read_file --path /tmp/file.txt"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    with open(args.path) as f:
        sys.stdout.write(f.read())


if __name__ == "__main__":
    main()
