# Exception classes of a module, caught by their class or a base, derived from in the main
# program; one nothing catches ends the program with "module.Class: str(e)".
from mods.errs import Full, Missing, Store, StoreError, checked
import mods.errs


class Readonly(mods.errs.StoreError):
    def __init__(self, what: str):
        super().__init__(what)
        self.what = what


class Gone(Missing):
    def __repr__(self) -> str:
        return f"Gone({self.key!r})"


def write(s: Store, k: str, v: int, ro: bool) -> None:
    if ro:
        raise Readonly(k)
    s.put(k, v)


s = Store(2)
write(s, "a", 1, False)
print(checked(s, "a"), checked(s, "b"))
for k, ro in [("b", False), ("c", False), ("d", True)]:
    try:
        write(s, k, 0, ro)
        print("wrote", k)
    except Full as e:
        print("full:", e, repr(e), e.size)
    except StoreError as e:
        print("store error:", repr(e))
try:
    s.get("zz")
except mods.errs.StoreError as e:
    print("caught by module attribute:", e)
try:
    s.get("q")
except (Full, Missing) as e:
    print("either:", e, repr(e))
try:
    write(s, "e", 1, True)
except Readonly as e:
    print("readonly:", e.what, repr(e))
try:
    raise Gone("old")
except Missing as e:
    print("gone:", e, repr(e), e.key)
nothing: list[Missing | None] = [None]
try:
    raise nothing[0]
except TypeError as e:
    print("TypeError:", e)
try:
    print(sorted([Gone("b"), Gone("a")]))
except TypeError as e:
    print("TypeError:", e)
print(s.get("missing"))
