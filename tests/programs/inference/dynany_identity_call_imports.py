# pystachy: dynamic-any
from typing import Any, Callable

import dynidentitycalls as typed
from dynidentitycalls import keep_float


number = int("1000")
original: Any = number
result: Any = typed.keep_int(number)
print("imported int", result is number, id(result) == id(original))
value = float("nan")
direct: Any = keep_float(value)
qualified: Any = typed.keep_float(value)
fn: Callable[[float], float] = keep_float
indirect: Any = fn(value)
print("imported float", direct is value, qualified is value, indirect is value)
first: Any = typed.default()
second: Any = typed.default()
print("imported default", first is second, first is typed.VALUE)
items: set[Any] = {value, direct, qualified, indirect}
print("imported nan keys", len(items))

pair = typed.Pair()
a: Any = pair.a
b: Any = pair.b
print("imported constructor aliases", a is b, id(a) == id(b))
read = typed.capture(value)
held: Any = read()
print("imported closure", held is value, read() is held)
empty = typed.capture(None)
print("imported closure None", empty() is None)
