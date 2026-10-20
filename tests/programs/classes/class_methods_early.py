# A static or class method that module code calls through its class before a global it reads is
# assigned raises CPython's NameError (the call runs user code, as a function's does)
class K:
    @staticmethod
    def show() -> None:
        print("show", G)

    @classmethod
    def make(cls) -> "K":
        print("make")
        return cls()


k = K.make()
K.show()
G = 1
