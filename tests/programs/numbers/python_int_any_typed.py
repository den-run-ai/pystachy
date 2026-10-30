# pystachy: python-int
# The inverse module arrangement: promoting entry code calls a dynamic helper.
from any_wide_bridge import box, describe, same

value = 2 ** 70
wrapped = box(value)
print(describe(value), describe(-value))
print(wrapped == value, value == wrapped, wrapped < value + 1, value - 1 < wrapped)
print(same(wrapped, value), same(value, value))
restored: int = wrapped
optional: int | None = wrapped
print(restored, optional, same(restored, wrapped), same(optional, wrapped))
print(restored * 2, optional + 1 if optional is not None else 0)
print(int(wrapped), float(wrapped))
print(same(int(wrapped), wrapped), same(box(int(wrapped)), wrapped))
