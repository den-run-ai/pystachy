# x & y where a side wraps (masked arithmetic) and the result is wanted as a closed union: a
# conditional or boolean operand keeps its scalar type (see scalar_union_conditional_operand.py)
def masked(a: int, b: int, c: bool) -> int | float:
    return ((a if c else 2) or b) & ((b + a) * 3 - 4)


def masked_tree(a: int, b: int, c: bool) -> int | str:
    return ((a if c else b) * 2654435761 + (b if c else a)) & 0xFFFFFFFF


print(masked(6, 9, True), masked(6, 9, False), masked(0, 5, True), masked_tree(123456789, 987654321, True), masked_tree(123456789, 987654321, False))
