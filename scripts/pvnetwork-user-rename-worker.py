#!/usr/bin/env python3
import argparse
from backend.user_rename.worker import run_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="process at most one rename job")
    parser.parse_args()
    state = run_once()
    if state == "error":
        return 1
    if state:
        print(f"RENAME_JOB_STATE={state}")
    else:
        print("RENAME_JOB_STATE=idle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
