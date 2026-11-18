# error: object_sentinel_shadow_param.py:8: error: expected object, got int
# CPython prints True False False: f's parameter S is another object, so x = 1 runs only where x is that object
S = object()


def f(x: int = S, S: object = S) -> bool:
    if x is S:
        x = 1
    return type(x) is object


print(f(S=object()), f(), f(4))
