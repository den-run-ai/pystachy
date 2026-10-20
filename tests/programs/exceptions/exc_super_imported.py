# super(C, self) in the methods of exception classes of imported modules, where C names the
# module's own class: mods/supers.py imported as the package's submodule mods.supers and, from
# the module path that tests/programs/exceptions/exc_super_imported.path sets, as the module supers (two modules,
# each with its own classes); and in the main program, for a class named as a builtin.
from mods.supers import Bad, Full, Missing, StoreError
import mods.supers
import supers


class TimeoutError(Exception):
    def __init__(self, n: int):
        super(TimeoutError, self).__init__(f"after {n}s")
        self.n = n


class Gone(Missing):
    def __init__(self, key: str):
        super(Gone, self).__init__(key + "!")

    def more(self) -> str:
        return "gone, " + super(Gone, self).detail()


try:
    raise Bad({1: 2})
except ValueError as e:
    print(e, repr(e))
for err in [Missing("a"), Gone("b")]:
    try:
        raise err
    except Missing as e:
        print(e, "|", repr(e), "|", e.code, "|", e.detail())
try:
    raise Full(3)
except StoreError as e:
    print(e, "|", repr(e), "|", e.code, "|", e.describe())
f = Full(4)
g = Gone("c")
print(f.detail(), "|", g.more())
try:
    raise supers.Missing("d")
except mods.supers.StoreError:
    print("not this one")
except supers.Missing as e:
    print("supers:", e, repr(e), e.detail())
print(StoreError.plain(Missing("e")), "|", supers.StoreError.basic(supers.Full(6)))
print(supers.Missing("f").static())
try:
    raise TimeoutError(5)
except TimeoutError as e:
    print(e, repr(e), e.n)
raise supers.Full(9)
