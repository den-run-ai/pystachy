# error: ThreadPoolExecutor.__init__() got an unexpected keyword argument 'initializer'
from concurrent.futures import ThreadPoolExecutor


def setup() -> None:
    print("setup")


with ThreadPoolExecutor(max_workers=1, initializer=setup) as pool:
    print(pool.submit(len, "ab").result())
