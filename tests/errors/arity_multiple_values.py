# error: h() got multiple values for argument 'a'
def h(a: int, b: int, c: int) -> int:
    return a


print(h(1, 2, 3, 4, a=1))
