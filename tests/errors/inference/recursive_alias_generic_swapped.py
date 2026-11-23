# error: recursive type aliases are not supported: 'Swap' refers to itself
# A generic recursive alias names itself with its own parameters, in their order (CPython prints 0)
type Swap[F, G] = F | G | list[Swap[G, F]]


def g(v: Swap[int, str]) -> int:
    return 0


print(g(1))
