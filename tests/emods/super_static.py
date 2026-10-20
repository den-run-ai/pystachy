# super() in a static method without parameters: CPython raises RuntimeError (super(): no arguments)


class E(ValueError):
    @staticmethod
    def make() -> str:
        return super().__str__()
