# error: expected int, got slice
class C:
    def __getitem__(self, k: int) -> int:
        return 1


print(C()[1:2])
