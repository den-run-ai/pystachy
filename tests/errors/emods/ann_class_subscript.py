class Box:
    def __class_getitem__(cls, item):
        print("class_getitem ran")
        return cls


class Holder:
    "CPython calls Box.__class_getitem__ when the class body runs"
    x: Box[int] = 0

    def get(self, *a):
        return a
