# A module that does not opt in to promoting ints, whose classes' comparison methods take a 64-bit
# int (tests/programs/numbers/python_int_object_compare.py).


class Fixed:
    def __eq__(self, other: int) -> bool:
        print("  Fixed.eq", other)
        return other == 3


class FixedOrder:
    def __init__(self, x: int) -> None:
        self.x = x

    def __lt__(self, other: int) -> bool:
        print("  FixedOrder.lt", other)
        return self.x < other

    def __ge__(self, other: int) -> bool:
        print("  FixedOrder.ge", other)
        return self.x >= other
