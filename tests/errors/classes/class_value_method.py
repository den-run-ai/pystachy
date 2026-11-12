# error: area() called through a class object (type[Shape]) is supported for class methods and static methods: call a method on its object, o.area()
# CPython calls the function of the class the value is with the object given (printing 4.0)
class Shape:
    def area(self) -> float:
        return 0.0


class Square(Shape):
    def area(self) -> float:
        return 4.0


def area_of(k: type[Shape], o: Shape) -> float:
    return k.area(o)


print(area_of(Square, Square()))
