#!/usr/bin/env python3
"""Minimal simulator entrypoint used by CI."""

from __future__ import annotations

import argparse
import os
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a simple simulator loop.")
    parser.add_argument(
        "--run-seconds",
        type=float,
        default=None,
        help="Exit after this many seconds. If omitted, run forever.",
    )
    return parser.parse_args()


def is_dry_run() -> bool:
    return os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    args = parse_args()
    dry_run = is_dry_run()

    start = time.monotonic()
    iterations = 0

    while True:
        iterations += 1
        mode = "DRY_RUN" if dry_run else "LIVE"
        print(f"[{mode}] simulation tick {iterations}", flush=True)

        if args.run_seconds is not None and (time.monotonic() - start) >= args.run_seconds:
            print("Reached requested runtime; exiting.", flush=True)
            break

        time.sleep(1)


if __name__ == "__main__":
    main()
