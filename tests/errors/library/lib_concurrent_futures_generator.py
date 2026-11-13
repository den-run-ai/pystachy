# error: type(x).__name__ of Generator[int] is not supported
from concurrent.futures import ThreadPoolExecutor


def evens(n: int):
    for i in range(n):
        yield i * 2


with ThreadPoolExecutor(max_workers=1) as pool:
    print(list(pool.submit(evens, 3).result()))
