from ffi import export


@export
def fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


print("module name:", __name__)
if __name__ == "__main__":
    print("self-test:", fib(10))
