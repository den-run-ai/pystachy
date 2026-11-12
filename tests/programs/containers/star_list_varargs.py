# f(*xs) of a list known only at run time, into a function of the program that takes *args: the
# list's first items fill the positional parameters before *args, and the others make the tuple
# *args is (a tuple[T, ...] of the list's item type), a copy that later changes to the list do
# not change. Too few items raise CPython's TypeError, after the call's other arguments are
# evaluated. A runtime-length tuple unpacks so too; a fixed tuple's items still pass as they are.
# Items may be numbers, strings, objects or coroutines (asyncio.gather(*coros)).
import types


def total(*args: int) -> int:
    return sum(args)


xs = [1, 2, 3]
print(total(*xs), total(*xs[:0]), total(*(4, 5)))


def pair(a, b, *rest):
    print(a, b, rest, len(rest))
    for r in rest:
        print("rest", r)
    return a + b


print(pair(*[1, 2, 3, 4]))
print(pair(10, *xs))
ys: list[int] = []
for n in range(4):
    try:
        print(pair(*ys))
    except TypeError as e:
        print("TypeError", e)
    ys.append(n)


def tagged(*names, sep: str) -> str:
    return sep.join(names)


def side(s: str) -> str:
    print("evaluated", s)
    return s


words = "a b c".split()
print(tagged(*words, sep=side("-")), tagged(*words[:0], sep="+"))
t = tuple(xs)
print(total(*t), pair(*t))
held = [7, 8]


def keep(*args: int) -> tuple[int, ...]:
    held.append(9)
    return args


print(keep(*held), held)


class Obj:
    def __init__(self, k: int) -> None:
        self.k = k


def objs(*os: Obj) -> int:
    return sum([o.k for o in os])


print(objs(*[Obj(1), Obj(2)]))


@types.coroutine
def pause():
    yield None


async def work(i: int) -> int:
    await pause()
    return i * 10


async def gather(*aws):
    out: list[int] = []
    for a in aws:
        out.append(await a)
    return out


async def main() -> None:
    print(await gather(*[work(i) for i in range(3)]))


c = main()
try:
    while True:
        c.send(None)
except StopIteration:
    print("done")
