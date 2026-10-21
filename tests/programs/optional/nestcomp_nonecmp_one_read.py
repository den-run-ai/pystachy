# Acceptance control for #822: the only truth test sees None. Resetting nested
# compilation state must preserve this previously accepted program's behavior.
# A multi-iteration version exposes the separate stale-None miscompilation.
def g(n):
    y = None
    for i in range(n):
        if y:
            print("y is truthy")
        else:
            print("y is falsy")
        w = i * 10 + 5
        y = w


def f():
    x = None
    if x is None:
        print("x is None")
    x = g(1)
    if x is None:
        print("x still None")


f()
