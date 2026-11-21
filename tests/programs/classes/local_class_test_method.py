# A test method that one call runs (as tools/cpython_test_methods.py writes its programs) defines a
# dataclass, an exception class, an enum class and a subclass, whose __qualname__ names the method
from dataclasses import dataclass
from enum import Enum


class Base:
    def describe(self) -> str:
        return "base"


class TestThings:
    def __init__(self) -> None:
        self.n = 2

    def test_classes(self) -> None:
        @dataclass
        class Point:
            x: int
            y: int = 0

        class MyError(ValueError):
            pass

        class Color(Enum):
            RED = 1
            BLUE = 2

        class Sub(Base):
            def describe(self) -> str:
                return "sub " + super().describe()

        p = Point(1)
        print(p, p == Point(1), Point(2, 3).y, repr(Point))
        try:
            raise MyError("boom")
        except MyError as e:
            print("caught", type(e).__name__, type(e).__qualname__, e)
        print(Color.RED, Color(2), list(Color), Color.RED.name)
        print(Sub().describe(), self.n)


def _TestThings__test_classes() -> None:
    t = TestThings()
    t.test_classes()
    print("ok TestThings.test_classes")


_TestThings__test_classes()
