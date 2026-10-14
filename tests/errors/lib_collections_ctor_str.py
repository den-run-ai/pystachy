# error: tests/errors/lib_collections_ctor_str.py:4: error: deque() cannot bind its type variables from the argument for 'iterable', a str: it does not fit the parameter's annotation (or that annotation's type variables are not supported there: they are in T, list[T], dict[K, V], set[T], tuple[T, *Ts], T | None and Callable[[T, *Ts], R]) (specializing collections.deque(str, int | None) for the call at tests/errors/lib_collections_ctor_str.py:4)
# compiled deque constructors need a list with a known item type
from collections import deque
print(deque("abc"))
