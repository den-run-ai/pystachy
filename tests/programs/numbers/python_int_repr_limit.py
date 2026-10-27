# pystachy: python-int
# repr() of a container whose int has more digits than CPython's limit for an int's text raises
# CPython's ValueError, which try catches: a list's item, a dict's value, and the containers that
# hold them.
def show(what: str, d: dict[int, int]) -> None:
    try:
        print(what, len(repr(d)))
    except ValueError as e:
        print(what, "ValueError:", str(e)[:40])


huge = 10 ** 5000
xs = [1, huge]
d = {1: 2, 3: huge}
named = {"huge": huge}
show("4300 digits", {1: 10 ** 4299})
show("parameter", d)
try:
    print(len(repr(xs)))
except ValueError as e:
    print("list ValueError:", str(e)[:40])
try:
    print(len(repr(d)))
except ValueError as e:
    print("dict ValueError:", str(e)[:40])
try:
    print(len(str(named)))
except ValueError as e:
    print("str keys ValueError:", str(e)[:40])
try:
    print(len(repr([d])))
except ValueError as e:
    print("list of dicts ValueError:", str(e)[:40])
try:
    print(len(f"{ {0: xs} }"))
except ValueError as e:
    print("dict of lists ValueError:", str(e)[:40])
try:
    print(d)
except ValueError as e:
    print("print ValueError:", str(e)[:40])
d[3] = 4
print(d, repr(xs[:1]))
