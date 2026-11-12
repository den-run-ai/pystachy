# error: reading inherited exception args through Parent is not supported when a subclass overrides args; catch the concrete user exception class
# pystachy: dynamic-any
class Parent(Exception):
    pass


class Child(Parent):
    @property
    def args(self) -> tuple[int, int]:
        return (7, 8)


try:
    raise Child(1)
except Parent as error:
    print(error.args)
