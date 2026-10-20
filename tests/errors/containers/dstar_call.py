# error: dstar_call.py:7: error: ** of a dict[str,int] is not supported: of a function's **kwargs, or a dict display with str keys, it is
def two(a: int, b: int) -> int:
    return a + b


d = {"a": 1, "b": 2}
print(two(**d))
