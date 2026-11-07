"""rwbench: the time csv.reader takes to read a CSV file into rows, and to parse the file's lines
already in memory, and the time csv.writer takes to write the rows to another file, per row; the
copy is read back and compared.

usage: python3 rwbench.py FILE COPY
"""
import csv
import sys
import time


def main() -> None:
    t = time.perf_counter()
    with open(sys.argv[1], newline="") as f:
        rows = list(csv.reader(f))
    read = time.perf_counter() - t
    with open(sys.argv[1], newline="") as f:
        lines = f.readlines()
    t = time.perf_counter()
    parsed = list(csv.reader(lines))
    parse = time.perf_counter() - t
    same = parsed == rows
    lines = []
    parsed = []  # (the memory they hold is free for what follows)
    t = time.perf_counter()
    with open(sys.argv[2], "w", newline="") as f:
        csv.writer(f).writerows(rows)
    written = time.perf_counter() - t
    with open(sys.argv[2], newline="") as f:
        same = same and list(csv.reader(f)) == rows
    n = len(rows)
    if not same:
        raise ValueError("CSV read, parse and write results differ")
    print(f"{n} rows, read back as written")
    print(f"read {read * 1e6 / n:.3f} us/row, parse {parse * 1e6 / n:.3f} us/row, write {written * 1e6 / n:.3f} us/row")


if __name__ == "__main__":
    main()
