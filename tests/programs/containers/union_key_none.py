# Class-union tables admit None, whose membership and missing-key repr must not
# dereference a union box. Regressions for both review findings on #1475.
class A:
    pass


class B:
    pass


a = A()
b = B()
d: dict[A | B, int] = {a: 1, b: 2, None: 3}
s: set[A | B] = {a, b, None}
print(None in d, None not in d, None in s, None not in s)
print(d[None], d.get(None), d.pop(None), None in d, None in s)
s.remove(None)
print(None in s, a in s, b in s, A() in s)
d.clear()
for operation in (0, 1, 2):
    try:
        if operation == 0:
            print(d[None])
        elif operation == 1:
            del d[None]
        else:
            d.pop(None)
    except KeyError as error:
        print("KeyError", error, repr(error))
print(d.get(None), None in d, d.setdefault(None, 4), d[None])
s.add(None)
print(None in s, len(s), None in s.copy())
s.discard(None)
s.discard(None)
print(None in s, len(s))
s.update([None])
print(None in s, len(s))
s.difference_update([None])
print(None in s, len(s))
