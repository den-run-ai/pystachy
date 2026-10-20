# A loop over vars(o) or o.__dict__ steps through CPython's live __dict__: assigning a field that
# __init__ left unassigned adds a key, and the iterator's next step raises RuntimeError (break
# takes no step); fields assigned in __init__ only change their values, which later steps read
class A:
    def __init__(self, f: bool) -> None:
        self.x = 1
        self.z = 3
        if f:
            self.y = 2


a = A(True)
for k, v in vars(a).items():
    print(k, v)
    a.z = 30
    a.x = 10
b = A(False)
try:
    for k in vars(b):
        print(k)
        b.y = 5
except RuntimeError as e:
    print("RuntimeError:", e)
print(vars(b))
c = A(False)
for k in vars(c):
    if k == "z":
        c.y = 1
        break
print(vars(c))
d = A(False)
try:
    for k, v in d.__dict__.items():
        if k == "z":
            d.y = 7
except RuntimeError as e:
    print("RuntimeError:", e)
print(d.__dict__)
e = A(False)
for v in vars(e).values():
    print(v)
print(vars(e))
