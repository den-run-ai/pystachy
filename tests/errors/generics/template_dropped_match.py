# error: local variable 'x' is read before its first assignment
# A match statement's capture in the branch that isinstance() drops still makes x a local of k
# (CPython: UnboundLocalError), not the module's x.
x = 3


def k(a):
    if isinstance(a, str):
        match a:
            case [x, *_]:
                pass
    return x


print("start")
print(k(1))
