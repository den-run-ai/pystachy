"""CLI for the unchanged socket consumer; build only bench_workload for extensions."""

import sys

from bench_workload import run

if len(sys.argv) != 5:
    raise ValueError("usage: bench_driver.py CASE ITERATIONS WARMUPS SAMPLES")
run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
