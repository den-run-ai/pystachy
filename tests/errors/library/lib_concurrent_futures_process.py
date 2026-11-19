# error: 'ProcessPoolExecutor' from 'concurrent.futures' is not supported
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor(2) as pool:
    print(pool.submit(len, "ab").result())
