# pystachy: python-int
# Inference must revisit every tuple position: the first pass promotes only the
# arithmetic result, then reading that position promotes the preceding one (#1030).
def grow_for(n: int) -> int:
    t = (1, 2)
    for i in range(n):
        t = (t[1], t[0] + t[1] * 3)
    return t[1]


print(grow_for(40), grow_for(0))


def grow_while(n: int) -> int:
    t = (1, 2)
    i = 0
    while i < n:
        new = t[0] + t[1] * 3
        t = (t[1], new)
        i += 1
    return t[1]


print(grow_while(40), grow_while(1))

g_for = (1, 2)
for i in range(40):
    g_for = (g_for[1], g_for[0] + g_for[1] * 3)
print(g_for)

g_while = (1, 2)
i = 0
while i < 40:
    g_while = (g_while[1], g_while[0] + g_while[1] * 3)
    i += 1
print(g_while)


def nested(n: int) -> int:
    t = ((1, 2), True, "kept", 1.25)
    for i in range(n):
        t = ((t[0][1], t[0][0] + t[0][1] * 3), not t[1], t[2], t[3])
    print(t)
    return t[0][1]


print(nested(40))


def minimum(n: int) -> int:
    # A tuple with one promoting item already present, including the sentinel
    # value used by its physical representation, still widens its other item.
    t = (-9223372036854775808, 2)
    for i in range(n):
        t = (t[1], t[0] + t[1] * 3)
    return t[1]


print(minimum(3), minimum(0))
