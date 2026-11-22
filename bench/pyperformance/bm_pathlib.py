"""
Test the performance of pathlib operations.

This benchmark stresses the creation of small objects, globbing, and system
calls.
"""

# Python imports
import os
import pathlib
import shutil
import tempfile
import time  # Pystachy port: time.perf_counter() is pyperf.perf_counter()

TIMED: list[float] = []  # Pystachy port: the seconds of each timed part


NUM_FILES = 2000  # Pystachy port: the main replaces it for a smaller run


def generate_filenames(tmp_path, num_files):
    i = 0
    while num_files:
        for ext in [".py", ".txt", ".tar.gz", ""]:
            i += 1
            yield os.path.join(tmp_path, str(i) + ext)
            num_files -= 1


def setup(num_files):
    tmp_path = tempfile.mkdtemp()
    for fn in generate_filenames(tmp_path, num_files):
        with open(fn, "wb") as f:
            f.write(b'benchmark')

    return tmp_path


def bench_pathlib(loops, tmp_path):
    base_path = pathlib.Path(tmp_path)

    # Warm up the filesystem cache and keep some objects in memory.
    path_objects = list(base_path.iterdir())
    # FIXME: does this code really cache anything?
    # Pystachy port: there is no Path.stat() (nor os.stat()); here and below, exists()
    # makes the same stat() system call without building its result.
    for p in path_objects:
        p.exists()
    assert len(path_objects) == NUM_FILES, len(path_objects)

    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()

    for _ in range_it:
        # Do something simple with each path.
        for p in base_path.iterdir():
            p.exists()  # Pystachy port: for p.stat()
        for p in base_path.glob("*.py"):
            p.exists()  # Pystachy port: for p.stat()
        for p in base_path.iterdir():
            p.exists()  # Pystachy port: for p.stat()
        for p in base_path.glob("*.py"):
            p.exists()  # Pystachy port: for p.stat()

    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns
    # Pystachy port: the sorted names of both listings, for the check
    return sorted([p.name for p in base_path.iterdir()]), sorted([p.name for p in base_path.glob("*.py")])


if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of loops and argv[2] the number of files (upstream's 2,000 by default);
    # the listings are counted and their ends printed, and the time goes to stderr.
    import sys
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if len(sys.argv) > 2:
        NUM_FILES = int(sys.argv[2])
    tmp_path = setup(NUM_FILES)
    try:
        names, matches = bench_pathlib(loops, tmp_path)
    finally:
        shutil.rmtree(tmp_path)
    print("seconds", sum(TIMED), file=sys.stderr)
    print("pathlib", loops, NUM_FILES, len(names), names[0], names[-1], len(matches), matches[0], matches[-1],
          os.path.exists(tmp_path))
