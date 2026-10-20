# error: closure_two_lambdas.py:3: error: expected <function f.<locals>.<lambda> (tests/errors/language/closure_two_lambdas.py:3)>, got <function f.<locals>.<lambda> (tests/errors/language/closure_two_lambdas.py:3)> (each function is a type of its own
def f(n):
    return [lambda: n, lambda: n + 1]


print(len(f(1)))
