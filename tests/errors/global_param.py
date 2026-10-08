# error: name 'x' is parameter and global
def f(x: int) -> int:
    global x
    return x


print(f(1))
