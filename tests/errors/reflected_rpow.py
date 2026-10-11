# error: reflected_rpow.py:7: error: ** and pow() of objects are not supported (int ** V calls V.__rpow__)
class V:
    def __rpow__(self, k: int) -> int:
        return 7


print(2 ** V())
