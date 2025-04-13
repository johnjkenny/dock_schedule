#!/usr/bin/env python3

import sys


def main():
    print("Hello, World!")
    try:
        code = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    except ValueError:
        print("Invalid exit code. Defaulting to 1.")
        code = 1
    print(f"Exiting with code: {code}")
    sys.exit(code)


if __name__ == "__main__":
    main()
