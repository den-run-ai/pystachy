# error: name 'Optional' is not defined (import it from typing)
def f(p: Optional[int], xs: LIST[int]) -> int:
    return len(xs)


print(f(None, [1]))
