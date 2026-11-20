# error: class_nested_deco_name.py:10: error: decorator @Registry.add is not supported: it reads class Outer.Registry, which the class body around it nests
# A decorator in a class body that reads a class the body nests: CPython finds the nested class
# in the class scope there (this prints 1), which Pystachy does not see from a decorator.
class Outer:
    class Registry:
        @staticmethod
        def add(f: object) -> object:
            return f

    @Registry.add
    def m(self) -> int:
        return 1


print(Outer().m())
