# pystachy: dynamic-any
from typing import Any

xs: Any = [1, None, 'x']
it = iter(xs)
print(iter(it) is it, next(it))
xs.append(4)
print(list(it))
xs.append(5)
print(next(it, 'done'))
print(next(iter(xs)))
for v in reversed(xs):
    print('reverse', v)
r = reversed(xs)
print(iter(r) is r, next(r), list(r))
s: Any = 'aé🙂'
print(list(iter(s)), list(reversed(s)))
t: Any = (2, 3)
print(list(iter(t)), list(reversed(t)))
d: Any = {'a': 1, 'b': 2}
print(list(iter(d)), list(reversed(d)))
dit = iter(d)
print(next(dit))
d['c'] = 3
try:
    next(dit)
except RuntimeError as e:
    print(e)
for bad in [None, 3, 'x', [1]]:
    try:
        print(next(bad, 0))
    except TypeError as e:
        print(e)
