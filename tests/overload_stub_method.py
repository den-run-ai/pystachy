# An imported class whose @overload stub methods no def follows (also a special method's and a
# static method's) compiles, as CPython keeps the stubs: only a call of one is an error
# (tests/errors/import_overload_stub_method.py); a stub that a def replaces past other defs is dropped
from mods.stubbed import Pair

p = Pair(1, 2)
print(p.total(), p.total(3), p.size(), p.a, p.b)
