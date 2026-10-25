# pystachy: python-int
# Original integration cases. All expected output comes from builtin CPython int.
class Box:
    def __init__(self, value: int):
        self.value = value


def grow(x: int, step: int = 1) -> int:
    return x + step


def annotated(x: "int") -> "int":
    return x * x


def closure(x: int):
    def add(y: int) -> int:
        return x + y
    return add


x = 2 ** 128
alias = x
values: list[int] = [1, x, x + 1]
shared = values
shared[0] = grow(shared[1])
box = Box(x)
fn = closure(x)
counts: dict[int, int] = {x: 1, x + 1: 2}
seen: set[int] = {x, x + 1, x}
for i in range(300):
    scratch = [2 ** 256 + i, 2 ** 257 - i]
    assert scratch[0] + scratch[1] == 3 * 2 ** 256
assert alias == x
assert shared is values
assert values[0] == values[-1] == x + 1
assert counts[int(str(x))] == 1
assert len(seen) == 2 and int(str(x)) in seen
assert grow(box.value) == fn(1) == x + 1
assert annotated(x) == 2 ** 256
print(values, counts[x], sorted(seen), box.value, fn(3))
print(values[:2], values[-(2 ** 200):2 ** 200], values[::2 ** 100])
assert sum(values) == 3 * x + 2
print(sum(values), min(values), max(values), len(values) + x)
q, r = divmod(x, 3)
print(q, r)

caught = 0
try:
    values[2 ** 100]
except IndexError:
    caught += 1
try:
    values[-(2 ** 100)] = 0
except IndexError:
    caught += 1
assert caught == 2
print('index exceptions', caught)

start = 2 ** 100
assert list(range(start, start + 3)) == [start, start + 1, start + 2]
assert list(range(start, start - 3, -1)) == [start, start - 1, start - 2]
assert list(range(0)) == []
print(list(range(start, start + 3)), list(range(start, start - 3, -1)))
factorial = 1
for n in range(1, 101):
    factorial *= n
print('100!', factorial)
a = 0
b = 1
for i in range(200):
    a, b = b, a + b
print('Fibonacci(200)', a)
