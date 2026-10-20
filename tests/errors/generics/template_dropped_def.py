# error: local variable 'g' is read before its first assignment
# The def in the branch that isinstance() drops still makes g a local of k (CPython:
# UnboundLocalError), not the module's g.
def g() -> int:
    return 1


def k(s):
    if isinstance(s, str):
        def g() -> int:
            return 2
    return g()


print("start")
print(k(3))
