# error: field 'count' is outside __slots__ of 'Point'
class Point:
    __slots__ = ()
    count = 1

    def increment(self) -> None:
        self.count += 1


Point().increment()
