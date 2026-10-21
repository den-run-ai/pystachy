# An alias of a class through a module's attribute (#804) whose own base is read through a
# module's attribute too (class D(sh.Box)): the base is resolved as the alias is, so A = derived.D
# is an alias of the class
import mods.attralias_qderived as derived

A = derived.D


def make(n: int) -> A:
    return A(n)


a = make(4)
print(A.__name__, A.kind, a.v, a.twice(), isinstance(a, derived.D), type(a).__name__)
