# Parse the files named in mypy-files.txt (read first, so only parsing is timed) ROUNDS times
import binascii
import sys
import time

from ast_serialize import parse


def main() -> None:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    with open("mypy-files.txt") as f:
        names = [line.strip() for line in f if line.strip()]
    sources: list[bytes] = []
    for name in names:
        with open(name, "rb") as g:
            sources.append(g.read())
    best = 1e9
    total = 0
    crc = 0
    for r in range(rounds):
        t0 = time.perf_counter()
        total = 0
        crc = 0
        for i in range(len(names)):
            res = parse(names[i], sources[i], False, (3, 13), "linux", [], [], 5)
            total += len(res[0])
            crc = binascii.crc32(res[0], crc)
        t1 = time.perf_counter()
        if t1 - t0 < best:
            best = t1 - t0
    print(len(names), total, crc, "best %.4f s" % best)


main()
