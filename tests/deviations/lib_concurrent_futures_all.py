# Documented deviation: there is no ProcessPoolExecutor (lib/compatibility.md#concurrentfutures),
# so concurrent.futures.__all__ does not name it; CPython's does, and prints True twice
import concurrent.futures

print("ThreadPoolExecutor" in concurrent.futures.__all__)
print("ProcessPoolExecutor" in concurrent.futures.__all__)
