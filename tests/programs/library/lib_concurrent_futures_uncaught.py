# An exception of concurrent.futures that nothing catches is reported with CPython's name for
# its class, the module that defines it included
from concurrent.futures import Future

f = Future[int]()
f.cancel()
print("cancelled")
f.result()
