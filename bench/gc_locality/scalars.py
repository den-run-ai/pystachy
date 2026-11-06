"""Escaping scalar-only records, with small or address-shaped integer payloads.

CPython and native AOT: scalars.py ROUNDS WIDTH MODE (suggested: 40 100000 aligned).
The aligned values are synthetic integers, not pointers to heap allocations.
"""
import sys


class Record:
    def __init__(self, value: int, address: int):
        self.a = address
        self.b = address + 64
        self.c = address + 128
        self.d = address + 192
        self.e = value
        self.f = value + 1
        self.g = value + 2
        self.h = value + 3


def main():
    rounds = int(sys.argv[1])
    width = int(sys.argv[2])
    assert rounds > 0 and width > 0
    mode = sys.argv[3]
    assert mode == "small" or mode == "aligned"
    base = 0x0000550000000000 if mode == "aligned" else 0
    retained: list[Record] = []
    total = 0
    for r in range(rounds):
        records = [Record(i + r, base + ((i * 64) % 16777216)) for i in range(width)]
        for i in range(width):
            v = records[i]
            total += (v.a & 65535) + (v.b & 65535) + (v.c & 65535) + (v.d & 65535)
            total += v.e + v.f + v.g + v.h
        retained.append(records[r % width])
    for r in range(rounds):
        assert retained[r].e == r % width + r
        assert retained[r].a == base + ((r % width * 64) % 16777216)
    print("scalars", rounds, width, mode, total, len(retained))


main()
