from enum import Flag, IntFlag


class Strict(Flag):
    A = 1
    AC = 5
    ALSO_AC = AC
    B = 2


class Keep(IntFlag):
    A = 1
    AD = 9
    B = 2


print(list(Strict), len(Strict), Strict.AC is Strict.ALSO_AC)
print(list(Strict.AC), len(Strict.AC), Strict.A in Strict.AC)
# Each bit is looked up as the iterator advances. Looking up 4 creates and caches
# an unnamed member which the already-started iterator can now find.
it = iter(Strict.AC)
print(next(it) is Strict.A)
c = Strict(4)
print(c.name, repr(c), next(it) is c, list(Strict.AC), Strict(4) is c)
print(repr(Strict.AC | Strict.B), repr(~Strict.B))
for value in [6, 8]:
    try:
        print(Strict(value))
    except ValueError as exc:
        print(str(exc))
for mask in [9, 11, 8, 12, 16, -1]:
    flag = Keep(mask)
    print(flag.value, flag.name, repr(flag), list(flag), len(flag))


class CompositeOnly(Flag):
    BOTH = 3


print(list(CompositeOnly), len(CompositeOnly), list(CompositeOnly.BOTH))
print(CompositeOnly(1).name, CompositeOnly(2).name, list(CompositeOnly.BOTH))
