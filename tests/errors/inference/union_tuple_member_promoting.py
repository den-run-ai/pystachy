# error: tuple[int,str] of promoting ints in a closed union is not supported
# pystachy: python-int
# A union holds 64-bit ints: a tuple of promoting ints is no member (CPython prints (7, 'seven') 7)
def pick(k: int) -> int | tuple[int, str]:
    if k == 0:
        return 7
    return (7, "seven")


print(pick(1), pick(0))
