class V:
    def __rpow__(self, k: int) -> int:
        return 7


print(2 ** V())
