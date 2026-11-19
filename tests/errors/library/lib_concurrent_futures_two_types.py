# error: expected Future[int], got Future[str]
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=1) as pool:
    fs = [pool.submit(len, "ab"), pool.submit(str, 3)]
print([f.result() for f in fs])
