# error: complex_int_param.py:8: error: expected complex, got int
# (as an int is no float where a float is annotated: CPython would keep it an int, which prints as
# one; write complex(2))
def norm(z: complex) -> float:
    return abs(z)


print(norm(2))
