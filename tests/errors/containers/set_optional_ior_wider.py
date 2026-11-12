# error: set_optional_ior_wider.py:5: error: unsupported operand types for |=: set[str] and set[str | None] (a set holds elements of one type)
# (s -= t and s &= t take such a t; s |= t would add None to a set of strs)
s: set[str] = {"a"}
t: set[str | None] = {None}
s |= t
print(s)
