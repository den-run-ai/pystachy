class Helper:
    def key(self) -> int:
        print("key ran")
        return 0


class Sorted:
    order = sorted([3, 1], key=Helper.key)

    def get(self, *a):
        return a
