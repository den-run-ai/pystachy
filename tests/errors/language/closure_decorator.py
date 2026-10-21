# error: closure_decorator.py:7: error: down() reads its own name, which binds what its decorators give once they have run: not supported in a def inside a function
def identity(f):
    return f


def outer(n: int) -> int:
    @identity
    def down(k):
        return 0 if k == 0 else 1 + down(k - 1)
    return down(n)


print(outer(4))
