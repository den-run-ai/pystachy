class Helper:
    def key(self) -> int:
        print("key ran")
        return 0


class Sorted:
    order = sorted([3, 1], key=Helper.key)

    def __init__(self, *a):
        self.a = a
