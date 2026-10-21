# A module whose code raises is not imported: the name its import binds stays unbound (NameError,
# or UnboundLocalError in a function), and a later import runs its code again, as CPython removes
# the module from sys.modules.
for i in range(2):
    try:
        import mods.half
    except ValueError:
        print("failed", i)
try:
    print(mods.half.A)
except NameError as e:
    print("NameError:", e)


def load() -> int:
    try:
        import mods.half as h
    except ValueError:
        print("failed in load")
    return h.C


print(load())
import mods.half

print(mods.half.A, mods.half.B, mods.half.C, mods.half.__name__)
