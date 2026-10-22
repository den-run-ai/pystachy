# A nested compile once inherited an outer comparison's permission to read the global.
# Its generic setter reveals the payload type after the loop's earlier copy has compiled.
value = None


def set_value(v):
    global value
    value = v


def loop(n):
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
