"""Standalone script: python -m src.tools.cli.write_file --path /tmp/file.txt --content "hello" """
import argparse
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--content", required=True)
    args = parser.parse_args()
    with open(args.path, "w") as f:
        f.write(args.content)
    sys.stdout.write(f"Successfully wrote {len(args.content)} bytes to {args.path}")


if __name__ == "__main__":
    main()
