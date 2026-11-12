# error: obj_rpow_number.py:8: error: ** and pow() of objects are not supported (int ** Power calls Power.__rpow__)
# A reflected power is not called: only the other reflected arithmetic methods are.
class Power:
    def __rpow__(self, other: int) -> int:
        return other + 1


print(2 ** Power())
