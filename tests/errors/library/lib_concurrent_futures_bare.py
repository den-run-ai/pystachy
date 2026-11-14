# error: Future() does not bind its type variable '_T'
from concurrent.futures import Future

f = Future()
f.set_result(1)
print(f.result())
