# error: _chain() yields int, but yield from delegates to a generator that yields str
# itertools.chain() takes iterables of different types, but their items need one type: a
# generator yields one type (lib/compatibility.md)
from itertools import chain

print(list(chain([1, 2], ["a"])))
