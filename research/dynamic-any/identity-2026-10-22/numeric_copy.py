# pystachy: dynamic-any
# Monitoring probe: typed numeric recurrence with copies, no observable identity.
import sys
from time import perf_counter_ns, process_time_ns

def integer(n: int, seed: int) -> int:
    x = seed
    total = 0
    for i in range(n):
        x = (x * 17 + 3) % 1000003
        y = x
        total += y
    return total

def floating(n: int, seed: int) -> int:
    x = float(seed)
    total = 0
    for i in range(n):
        x = (x * 1.25 + 3.0) % 1000.0
        y = x
        total += int(y)
    return total

n = int(sys.argv[2])
seed = int(sys.argv[3])
start = perf_counter_ns()
cpu = process_time_ns()
value = integer(n, seed) if sys.argv[1] == 'int' else floating(n, seed)
cpu_end = process_time_ns()
end = perf_counter_ns()
print(value, end-start, cpu_end-cpu)
