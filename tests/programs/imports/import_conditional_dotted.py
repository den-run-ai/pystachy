# A function's import of mods.counter in a branch makes mods its local, unbound where the branch
# does not run (CPython: UnboundLocalError), though the module imports mods.counter too.
import mods.counter


def limit(flag: bool) -> int:
    if flag:
        import mods.counter
    return mods.counter.LIMIT


print(limit(True))
try:
    print(limit(False))
except UnboundLocalError as e:
    print("UnboundLocalError:", e)
