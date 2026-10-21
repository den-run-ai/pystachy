# A later loop store must revisit reads compiled while the payload type was unknown.
def direct(n):
    y = None
    for i in range(n):
        print("truthy" if y else "falsy")
        w = i * 10 + 5
        y = w
    print(y is None)


def nested_body(n):
    y = None
    for i in range(n):
        if y:
            print("truthy")
        else:
            print("falsy")
        w = i * 10 + 5
        y = w


def nested(n):
    x = None
    if x is None:
        print("x is None")
    x = nested_body(n)
    if x is None:
        print("x still None")


def zeros(n):
    y = None
    i = 0
    while i < n:
        print(bool(y), not y)
        w = i
        y = w
        i += 1
    # A fresh straight-line binding must retain its independent type.
    y = "done"
    print(y.upper())


for n in [0, 1, 3]:
    print("direct", n)
    direct(n)
    print("nested", n)
    nested(n)
    print("zero", n)
    zeros(n)
