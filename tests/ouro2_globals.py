count = 0
names: list[str] = []
LIMIT = 3


def bump() -> None:
    global count
    count += 1


def shadow() -> int:
    count = 100  # a local: the global is untouched
    return count + LIMIT


def record(s: str) -> None:
    names.append(s)  # mutating a global needs no declaration


def classify(n: int) -> str:
    if n < 0:
        return "neg"
    elif n == 0:
        return "zero"
    elif n < LIMIT:
        return "small"
    else:
        return "big"


for i in range(4):
    bump()
    record(classify(i - 1))
print(count, shadow(), count, len(names), names[0], names[1], names[2], names[3])
k: int
k = 5
print(k)
if count > 3: print("one-line if")
def f(a: int, b: int) -> int: return a * b
print(f(6, 7))
"""a docstring-style expression statement"""
