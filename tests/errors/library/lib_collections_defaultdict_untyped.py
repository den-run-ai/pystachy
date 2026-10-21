# error: defaultdict() cannot bind its type variables from the argument for 'default_factory', a <built-in function int>: a <built-in function int> is no def, lambda or Callable, whose signature Callable[[...], R] matches; or name them where the object goes (q: defaultdict[int, int] = defaultdict(...)) or in the call (defaultdict[int, int](...))
# A factory types the values at most: the keys need an annotation, d: defaultdict[str, int]
from collections import defaultdict

counts = defaultdict(int)
counts["a"] += 1
print(counts)
