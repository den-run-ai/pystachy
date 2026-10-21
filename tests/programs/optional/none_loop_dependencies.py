def returns_none():
    return None


def copies(n):
    y = None
    z = None
    for i in range(n):
        print("truthy" if y else "falsy")
        y = z
        w = i * 10 + 5
        z = w


def all_none(n):
    y = None
    for i in range(n):
        print("truthy" if y else "falsy")
        w = returns_none()
        y = w


def control_flow(n):
    y = None
    for i in range(n):
        print("truthy" if y else "falsy")
        w = i + 5
        y = w
        if i == 0:
            continue
        break
    print(y is None)


def unresolved_result():
    x = None
    a = None
    x = a
    return x


def initial_copy(n):
    z = None
    y = z
    for i in range(n):
        print("truthy" if y else "falsy")
        w = i + 5
        y = w
        q = None
        z = q


def returned_none(n):
    y = unresolved_result()
    for i in range(n):
        print("truthy" if y else "falsy")
        w = i + 5
        y = w


def parameter(y, n):
    for i in range(n):
        print("truthy" if y else "falsy")
        w = i + 5
        y = w


for n in [0, 1, 3]:
    print("copies", n)
    copies(n)
    print("none", n)
    all_none(n)
    print("control", n)
    control_flow(n)
    print("initial copy", n)
    initial_copy(n)
    print("returned None", n)
    returned_none(n)
    print("parameter", n)
    parameter(unresolved_result(), n)
