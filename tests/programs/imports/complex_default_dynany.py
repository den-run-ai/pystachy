# pystachy: dynamic-any
# A complex parameter whose default is a constant of another type (z: complex = 0), in a program
# that tracks numeric identity: a call that passes the argument compiles as it does without the
# pragma, in an imported module's def and in the program's own
import mods.complexdefaults as m


def local(z: complex = 0, scale: float = 2.0) -> complex:
    return z * scale


print(m.plain(3j), m.plain(z=1 + 2j), m.doubled(1j))
print(local(1j), local(2 + 1j, 0.5), local(z=3j))
