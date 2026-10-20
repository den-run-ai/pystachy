# error: isinstance() is only supported with the builtin types and classes as its second argument
# itertools.chain is an object whose calls make generators (lib/compatibility.md), not a class
import itertools

c = itertools.chain([1], [2])
print(isinstance(c, itertools.chain))
