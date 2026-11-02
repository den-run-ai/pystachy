import sys
from time import perf_counter_ns


class Counter:
    def __init__(self, value: int) -> None:
        self.value = value

    def update(self, delta: int) -> int:
        self.value = (self.value + delta) % 1009
        return self.value


def kernel(n: int) -> int:
    counters = [Counter(i) for i in range(64)]
    total = 0
    for step in range(n):
        for counter in counters:
            total += counter.update(step & 31)
    return total


n = int(sys.argv[1])
print("warm", kernel(n))
for sample in range(7):
    start = perf_counter_ns()
    result = kernel(n)
    elapsed = perf_counter_ns() - start
    print(result, elapsed)
