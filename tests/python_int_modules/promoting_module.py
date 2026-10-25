# pystachy: python-int

def factorial(n: int) -> int:
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
