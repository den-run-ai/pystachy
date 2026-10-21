# error: expected int, got object
# dict.get() with an object() default of another type than the dict's values would need a union (#251)
def lookup(d: dict[str, int], k: str) -> str:
    missing = object()
    v = d.get(k, missing)
    if v is missing:
        return "missing"
    return "found"


print(lookup({"x": 1}, "x"))
