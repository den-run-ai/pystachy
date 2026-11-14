# A set of a union of classes whose objects hash by identity (#1452): an object of either class
# is found, added once and discarded whether it is typed by its class or by the union; the
# elements iterate as union values that isinstance() tells apart
class Info:
    def __init__(self, name: str) -> None:
        self.name = name


class Alias:
    def __init__(self, target: str) -> None:
        self.target = target


a = Info("a")
b = Info("b")
x = Alias("x")
s: set[Info | Alias] = set()
s.add(a)
s.add(x)
s.add(a)
u: Info | Alias = b
s.add(u)
print(len(s), a in s, b in s, x in s, Alias("x") in s, Info("a") in s)
v: Info | Alias = x
print(v in s, u in s)
s.discard(b)
s.discard(Alias("y"))
print(len(s), b in s)
names = []
for e in s:
    if isinstance(e, Info):
        names.append("info " + e.name)
    else:
        names.append("alias " + e.target)
print(sorted(names))
t: set[Info | Alias] = {x, b}
only: set[Info | Alias] = {b}
print(len(s | t), len(s & t), len(s - t), len(t - s), s.isdisjoint(only))
same: set[Info | Alias] = {x, a}
print(s == same, s != t, same <= s, t <= s)
c = s.copy()
c.add(b)
print(len(c), len(s), b in c)
items: list[Info | Alias] = [a, x, a]
print(sorted([isinstance(e, Alias) for e in set(items)]), len(set(items)))
