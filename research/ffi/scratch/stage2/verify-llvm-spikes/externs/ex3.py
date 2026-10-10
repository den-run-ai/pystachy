def cfun(x: int) -> int:
    ...


def pys_len(x: int) -> int: ...


try:
    print(pys_len(3))
except RuntimeError as e:
    print("caught", e)
print(cfun(1))
