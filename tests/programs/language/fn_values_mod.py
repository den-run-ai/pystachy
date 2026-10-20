# Functions as values across modules: a function of another module passed, returned and called
# through, and a builtin as a parameter's default value there
import mods.fnvals
from mods.fnvals import apply, inc


def square(x):
    return x * x


print(apply(inc, 1), apply(square, 3, times=2), apply(mods.fnvals.inc, 10, 3))
print(mods.fnvals.apply_all([inc, inc, inc], 0), mods.fnvals.apply_all((square, square), 2))
print(mods.fnvals.default_key("four"), mods.fnvals.default_key([1, 2], key=sum), mods.fnvals.chooser("inc")(41))
g = mods.fnvals.inc
print(g(g(1)), apply(g, 5))
