# A method call through a class object reads the method before it evaluates the arguments: a
# class object without it raises AttributeError and the arguments are not evaluated, also where
# the source names the class object (type(1)).
class A:
    @staticmethod
    def make(n: int) -> int:
        return n * 2


def side() -> int:
    print("side")
    return 1


try:
    print(type(1).make(side()))
except AttributeError:
    print("AttributeError")
kinds: list[type] = [str, A, type(None)]
for k in kinds:
    try:
        print(k.make(side()))
    except AttributeError:
        print("AttributeError", k.__name__)
