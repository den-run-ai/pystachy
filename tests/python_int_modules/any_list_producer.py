# pystachy: python-int
# The same promoting producer as tests/python_int_modules/promoting_module.py.


def factorial(n: int) -> int:
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
