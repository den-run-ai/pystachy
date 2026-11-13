# Parse the files named in mypy-files.txt ROUNDS times; only the parse() calls are timed (the
# files are read before, and the checksum of the results is computed after)
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
    outs: list[bytes] = []
    for r in range(rounds):
        outs = []
        t0 = time.perf_counter()
        for i in range(len(names)):
            res = parse(names[i], sources[i], False, (3, 13), "linux", [], [], 5)
            outs.append(res[0])
        t1 = time.perf_counter()
        if t1 - t0 < best:
            best = t1 - t0
    total = 0
    crc = 0
    for o in outs:
        total += len(o)
        crc = binascii.crc32(o, crc)
    print(len(names), total, crc, "best %.4f s" % best)


main()
