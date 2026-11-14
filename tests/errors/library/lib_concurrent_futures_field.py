# error: cannot infer the type of field 'last'; annotate it
from concurrent.futures import ThreadPoolExecutor


class Jobs:
    def __init__(self) -> None:
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.last = self.pool.submit(len, "ab")


print(Jobs().last.result())
