# error: got list[int]
# A wrapper's caller cannot reinterpret a nonempty callee result.
def filled(n):
    return [n]


def forward(n):
    return filled(n)


result: list[str] = forward(1)
