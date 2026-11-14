# Metadata reads and replacements that worked before direct nullable class calls.
from contextlib import contextmanager
from typing import Iterator


class C:
    @contextmanager
    def scope(self, *args, n: int = 0) -> Iterator[int]:
        yield n + (max(args) if args else 0)


class D(C):
    @contextmanager
    def scope(self, *args, n: int = 0) -> Iterator[int]:
        yield n + (max(args) if args else 0) + 100


keyword_cm = C().scope(n=7)
print("keyword", keyword_cm.kwds["n"])
with keyword_cm as value:
    print("value", value)

args_cm = C().scope(0, 3)
print("last argument", args_cm.args[-1])
args_cm.args = (0, 7)
with args_cm._recreate_cm() as value:
    print("arguments", value)

cm = C().scope(n=7)
other = D().scope(n=9)
cm.kwds = other.kwds
with cm._recreate_cm() as value:
    print("keywords", value)
cm.func = other.func
recreated = cm._recreate_cm()
with recreated._recreate_cm() as value:
    print("function twice", value)

receiver = D()
base = C.scope(receiver, n=7)
derived = D.scope(receiver, n=9)
base.func = derived.func
with base._recreate_cm() as value:
    print("same receiver", value)

plain = C().scope(n=11)
plain.func = plain.func
with plain._recreate_cm() as value:
    print("same function", value)

# An exposed function call that both the original port and CPython accept.
class Exposed:
    @contextmanager
    def scope(self, *args, n: int = 0) -> Iterator[int]:
        yield n


exposed = Exposed().scope(n=13)
generator = exposed.func(Exposed(), n=13)
print("function call", next(generator))
generator.close()

# The port's private factory and setter storage do not change public reflection.
reflected = C().scope(n=17)
for name in vars(reflected):
    if name in ["func", "args", "kwds"]:
        print("metadata name", name)
    if name in ["_func", "_pys_factory", "_pys_func_changed"]:
        print("unexpected private name", name)
print("func listed", "func" in dir(reflected))
print("private fields", hasattr(reflected, "_func"), hasattr(reflected, "_pys_factory"))
