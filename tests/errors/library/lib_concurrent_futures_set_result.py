# error: expected tuple[int] | None, got tuple[str]
from concurrent.futures import Future

f = Future[int]()
f.set_result("one")
print(f.result())
