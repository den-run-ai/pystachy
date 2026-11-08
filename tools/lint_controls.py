"""Run exactly two independent hosted Lint suites from the repository root."""

import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def signal_groups(processes, signum):
    for process in processes:
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            pass


def stop(processes):
    running = [process for process in processes if process.returncode is None]
    # Let unittest finally blocks clean up their own fixtures first. Unlike a
    # shell background job, Popen preserves Python's normal SIGINT disposition.
    signal_groups(running, signal.SIGINT)
    deadline = time.monotonic() + 1
    while any(process.poll() is None for process in running) and time.monotonic() < deadline:
        time.sleep(.01)
    # A suite can exit before its children; finish every group we interrupted.
    signal_groups(running, signal.SIGKILL)
    for process in running:
        process.wait(timeout=5)


def run_controls(patterns):
    if len(patterns) != 2:
        raise ValueError("Lint requires exactly two hosted control suites")
    cancelled = 0

    def cancel(signum, _frame):
        nonlocal cancelled
        if not cancelled:
            cancelled = 128 + signum

    previous = {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, cancel)
        with tempfile.TemporaryDirectory(prefix="lint-controls-") as directory, ExitStack() as stack:
            processes, logs = [], []
            try:
                for index, pattern in enumerate(patterns):
                    if cancelled:
                        break
                    path = Path(directory) / f"{index}.log"
                    output = stack.enter_context(path.open("w"))
                    logs.append(path)
                    process = subprocess.Popen(
                        [sys.executable, "-m", "unittest", "discover", "-s", "tools", "-p", pattern],
                        stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                    # Signal handlers must not raise between launch and registration.
                    processes.append(process)
                while not cancelled and any(process.poll() is None for process in processes):
                    time.sleep(.05)
            finally:
                stop(processes)
                for path in logs:
                    with path.open() as output:
                        shutil.copyfileobj(output, sys.stdout)
            status = next((process.returncode for process in processes if process.returncode), 0)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return cancelled or (128 - status if status < 0 else status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patterns", nargs=2)
    return run_controls(parser.parse_args().patterns)


if __name__ == "__main__":
    raise SystemExit(main())
