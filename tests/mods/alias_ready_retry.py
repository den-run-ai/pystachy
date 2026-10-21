from mods import counter
from mods.alias_base import inc


def call() -> int:
    return alias(9)


n = counter.incr(1)
print("attempt", n)
try:
    print(call())
except NameError as e:
    print("NameError", e)
alias = inc
if n == 1:
    raise ValueError("retry")
