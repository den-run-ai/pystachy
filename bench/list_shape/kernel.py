"""Indexed element updates with repeated reads; inputs remain runtime values."""
import sys


def update(values: list[float], rounds: int) -> float:
    total = 0.0
    for _ in range(rounds):
        for i in range(len(values)):
            before = values[i]
            values[i] = before * 0.5 + 0.25
            total += before + values[i]
    return total


def read_only(values: list[float], rounds: int) -> float:
    total = 0.0
    for _ in range(rounds):
        for i in range(len(values)):
            total += values[i]
    return total


size = int(sys.argv[1]) if len(sys.argv) > 1 else 8192
rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
mode = sys.argv[3] if len(sys.argv) > 3 else "update"
values = [float(i % 16) * 0.125 for i in range(size)]
if mode == "update":
    print(update(values, rounds))
elif mode == "read":
    print(read_only(values, rounds))
else:
    raise ValueError("mode must be update or read")
