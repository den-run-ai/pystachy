# Counted tuple construction/coercion preserves values, but does not intern empties
# or preserve identity across fixed/count or scalar/optional-element representations.
def counted(items: list[int]) -> tuple[int, ...]:
    return tuple(items)


first = counted([])
second = counted([])
print("empty", first == second, first is second)
fixed = (1, 2)
converted: tuple[int, ...] = fixed
print("fixed", fixed == converted, fixed is converted)
source = counted([1, 2])
boxed: tuple[int | None, ...] = source
print("boxed", boxed == (1, 2), source is boxed)
print("same", tuple(source) is source)
