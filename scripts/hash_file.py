"""Print the SHA256 of an existing source file without changing it."""

import argparse
import sys
from pathlib import Path

from validate_manifest import sha256_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    try:
        print(sha256_file(args.file))
    except OSError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
