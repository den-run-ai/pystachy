# A key comparison that changes the source size aborts update, dict(source), and copy.
# Sparse sources make dict(source) and copy merge entries instead of cloning the table.
class X:
    def __init__(self, v: int) -> None:
        self.v = v

    def __hash__(self) -> int:
        return 0

    def __eq__(self, o: object) -> bool:
        if armed:
            other.clear()
        return False


armed = False
other: dict[X, int] = {}
for i in range(3):
    other[X(i)] = i
d = {X(-1): 0}
armed = True
try:
    d.update(other)
except RuntimeError as e:
    print("RuntimeError", e)
print(len(d), len(other))
armed = False
ks = [X(i) for i in range(6)]
for k in ks:
    other[k] = k.v
for k in ks[:3]:
    del other[k]
armed = True
try:
    c = dict(other)
    print(len(c))
except RuntimeError as e:
    print("RuntimeError", e)
armed = False
for k in ks:
    other[k] = k.v
for k in ks[:3]:
    del other[k]
armed = True
try:
    c = other.copy()
    print(len(c))
except RuntimeError as e:
    print("RuntimeError", e)
print(len(other))
