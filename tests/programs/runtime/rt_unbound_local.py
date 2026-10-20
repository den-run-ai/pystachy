def first_neg(xs: list[int]) -> int:
    for v in xs:
        if v < 0:
            found = v
            break
    return found


print(first_neg([3, -2]))
print(first_neg([1, 2]))
