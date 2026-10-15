# error: got list[int]
# An annotated empty result already has a fixed element type.
def typed(n) -> list[int]:
    return []


def forward(n):
    return typed(n)


result: list[str] = forward(1)
