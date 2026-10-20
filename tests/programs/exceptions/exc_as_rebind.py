# The name an except clause binds may be bound later (or before, in a loop) to a value of another type.
def f() -> None:
    try:
        raise ValueError("v")
    except ValueError as e:
        print(e)
    e = 5
    print(e)
    try:
        raise KeyError("k")
    except KeyError as e:
        print(repr(e))
    try:
        print(e)
    except UnboundLocalError as u:
        print("UnboundLocalError", u)
    e = 7
    print(e)
f()
try:
    raise ValueError("w")
except ValueError as g:
    print(g)
g = "str"
print(g)
for h in range(2):
    try:
        raise ValueError("h")
    except ValueError as h:
        print(h)
try:
    print(h)
except NameError as n:
    print("NameError", n)
