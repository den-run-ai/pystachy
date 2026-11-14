# error: cannot iterate over None
from concurrent.futures import ThreadPoolExecutor


def add(a: int, b: int, c: int, d: int, e: int) -> int:
    return a + b + c + d + e


with ThreadPoolExecutor(max_workers=1) as pool:
    for total in pool.map(add, [1], [2], [3], [4], [5]):
        print(total)
