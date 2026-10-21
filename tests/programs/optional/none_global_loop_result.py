# A callee can return the null-only provisional type. Replay must also type a global
# initially assigned that result, before a later template setter reveals its payload.
value = None


def nothing():
    result = None
    other = None
    result = other
    return result


def set_value(v):
    global value
    value = v


def loop(n):
    global value
    value = nothing()
    for i in range(n):
        copy = value
        if copy is None:
            print("none")
        else:
            print("value")
        next_value = i * 10 + 5
        set_value(next_value)


def outer():
    result = None
    if result is None:
        print("outer")
    result = loop(3)
    if result is None:
        print("still none")


outer()
