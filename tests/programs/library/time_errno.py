# The builtin time module (clocks, sleep) and errno (the platform error numbers)
import time
import errno
from errno import ENOENT, EEXIST
from time import perf_counter
t0 = time.time()
p0 = perf_counter()
time.sleep(0.05)
time.sleep(0)
dt = perf_counter() - p0
print(dt >= 0.04, dt < 2.0, time.time() >= t0, time.time_ns() > 1_600_000_000 * 10**9, time.monotonic_ns() > 0, time.process_time() >= 0.0)
print(errno.ENOENT, ENOENT, EEXIST, errno.EACCES, errno.EINVAL, errno.EPIPE)
print(isinstance(time.time(), float), isinstance(time.time_ns(), int))
time.sleep(-1)
