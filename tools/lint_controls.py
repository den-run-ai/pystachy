"""Run Lint's two hosted control suites, and optionally make targets, at once from the repository root.

Each suite is mostly one CPython process; three of them fit the runner's four CPUs (#1525).
"""

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


def suite_commands(patterns, make_targets=()):
    if len(patterns) != 2:
        raise ValueError("Lint requires exactly two hosted control suites")
    commands = [["make", *make_targets]] if make_targets else []
    return commands + [[sys.executable, "-m", "unittest", "discover", "-s", "tools", "-p", pattern]
                       for pattern in patterns]


def run_controls(patterns, make_targets=()):
    commands = suite_commands(patterns, make_targets)
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
                for index, command in enumerate(commands):
                    if cancelled:
                        break
                    path = Path(directory) / f"{index}.log"
                    output = stack.enter_context(path.open("w"))
                    logs.append(path)
                    process = subprocess.Popen(
                        command, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
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
    parser.add_argument("--make", default="", metavar="TARGETS",
                        help="space-separated make targets to run beside the two suites")
    parser.add_argument("patterns", nargs=2)
    arguments = parser.parse_args()
    return run_controls(arguments.patterns, arguments.make.split())


if __name__ == "__main__":
    raise SystemExit(main())
