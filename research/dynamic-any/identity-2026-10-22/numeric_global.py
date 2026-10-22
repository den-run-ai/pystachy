# pystachy: dynamic-any
# Monitoring probe: typed numeric recurrence with copies, no observable identity.
import sys
from time import perf_counter_ns, process_time_ns

G = 0
F = 0.0

def integer(n: int, seed: int) -> int:
    global G
    G = seed
    total = 0
    for i in range(n):
        G = (G * 17 + 3) % 1000003
        total += G
    return total

def floating(n: int, seed: int) -> int:
    global F
    F = float(seed)
    total = 0
    for i in range(n):
        F = (F * 1.25 + 3.0) % 1000.0
        total += int(F)
    return total

n = int(sys.argv[2])
seed = int(sys.argv[3])
start = perf_counter_ns()
cpu = process_time_ns()
value = integer(n, seed) if sys.argv[1] == 'int' else floating(n, seed)
cpu_end = process_time_ns()
end = perf_counter_ns()
print(value, end-start, cpu_end-cpu)
