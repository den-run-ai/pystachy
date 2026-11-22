# Repeated calls reuse a tuple slot. A callee that saves *args must copy it first.
saved: list[tuple[int, int]] = []


def remember(*key: int) -> None:
    saved.append(key)


def visit(n: int) -> None:
    if n:
        remember(n, n + 1)
        visit(n - 1)


for size in range(1, 4):
    visit(size)
print(saved)
