# error: closure_arity.py:5: error: f.<locals>.inner() takes 1 positional argument but 2 were given
def f(n):
    def inner(k):
        return k + n
    return inner(1, 2)


print(f(1))
