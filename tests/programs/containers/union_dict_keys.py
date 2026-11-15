# A dict keyed by a union of classes whose objects hash by identity (#1452), as mypy's
# dict[str, set[TypeAlias | TypeInfo]] holds them: a key of either class, typed by its class or
# by the union, stores, finds, gets and pops one entry; a missing key raises KeyError
class Node:
    pass


class TypeInfo(Node):
    def __init__(self, name: str) -> None:
        self.name = name


class TypeAlias(Node):
    def __init__(self, target: str) -> None:
        self.target = target


i = TypeInfo("i")
j = TypeInfo("j")
t = TypeAlias("t")
d: dict[TypeInfo | TypeAlias, int] = {}
d[i] = 1
d[t] = 2
d[i] = 3
k: TypeInfo | TypeAlias = j
d[k] = 4
print(len(d), d[i], d[t], d[j], i in d, TypeInfo("i") in d, k in d)
print(d.get(t), d.get(TypeAlias("t")), d.get(TypeAlias("u"), -1))
print(d.pop(j), len(d), j in d)
try:
    print(d[j])
except KeyError:
    print("KeyError")
del d[t]
print(len(d), [isinstance(key, TypeInfo) for key in d])
deps: dict[str, set[TypeAlias | TypeInfo]] = {"T": set()}
deps["T"].add(i)
deps["T"].add(t)
deps["T"].add(i)
print(len(deps["T"]), t in deps["T"], j in deps["T"])
