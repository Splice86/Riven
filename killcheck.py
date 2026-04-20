#!/usr/bin/env python3
"""Check if a process is still running by PID.

Usage:
    python killcheck.py 12345
    python killcheck.py 12345 67890   # check multiple
"""

import os
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: python killcheck.py <pid> [<pid> ...]")
        sys.exit(1)

    for arg in sys.argv[1:]:
        try:
            pid = int(arg)
        except ValueError:
            print(f"{arg}: not a valid integer")
            continue

        try:
            os.kill(pid, 0)  # signal 0 just checks if process exists
            print(f"{pid}: running")
        except ProcessLookupError:
            print(f"{pid}: not running (ProcessLookupError)")
        except PermissionError:
            print(f"{pid}: running (permission denied to send signal, but process exists)")
        except Exception as e:
            print(f"{pid}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
