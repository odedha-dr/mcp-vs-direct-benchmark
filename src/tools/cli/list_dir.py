"""Standalone script: python -m src.tools.cli.list_dir --path /tmp"""
import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    entries = os.listdir(args.path)
    sys.stdout.write("\n".join(entries))


if __name__ == "__main__":
    main()
