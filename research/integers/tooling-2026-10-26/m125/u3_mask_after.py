MASK62 = (1 << 62) - 1


def djb2_62(s: str) -> int:
    h = 5381
    for c in s:
        h = ((h << 5) + h + ord(c)) & MASK62
    return h


print(djb2_62("ab"))
print(djb2_62("abcdefghijklmnop"))
