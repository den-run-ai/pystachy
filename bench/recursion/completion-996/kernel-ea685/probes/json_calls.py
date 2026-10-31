import json
import sys
from time import perf_counter_ns


def kernel(text: str, n: int) -> int:
    total = 0
    for i in range(n):
        result = json.loads(text)
        if isinstance(result, dict):
            total += len(result)
    return total


text = "{" + ",".join(['"key' + str(i) + '":' + str(i) for i in range(32)]) + "}"
n = int(sys.argv[1])
print("warm", kernel(text, n))
for sample in range(7):
    start = perf_counter_ns()
    result = kernel(text, n)
    elapsed = perf_counter_ns() - start
    print(result, elapsed)
