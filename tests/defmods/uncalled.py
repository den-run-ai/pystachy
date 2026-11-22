# Classes that define special methods Pystachy never calls, which CPython calls implicitly
# (__new__, __getattribute__, __setattr__, __delattr__; an ordinary class's __getattr__ alone is
# called, #1536), are errors only where the program uses them: an import runs none of their code,
# but their class bodies run, as in CPython.
def note(what: str) -> int:
    print(what)
    return 0


class Counted:
    made = note("the body of Counted runs")

    def __new__(cls, n: int) -> "Counted":
        Counted.made += 1
        return object.__new__(cls)

    def __init__(self, n: int) -> None:
        self.n = n


class Proxy:
    def __init__(self) -> None:
        self.hits = 0

    def __getattr__(self, name: str) -> int:
        return -1

    def __getattribute__(self, name: str) -> int:
        return object.__getattribute__(self, name)

    def __setattr__(self, name: str, v: int) -> None:
        object.__setattr__(self, name, v + 1)

    def __delattr__(self, name: str) -> None:
        print("kept", name)


class Failed(Exception):
    def __new__(cls, msg: str) -> "Failed":
        return super().__new__(cls, msg)


class Retry(Failed):
    "inherits Failed.__new__"


class Sealed:
    "a class attribute binds the hook as a def does"
    __setattr__ = 0

    def __init__(self) -> None:
        self.x = 1


class Mixed:
    "a field whose type Pystachy cannot infer too: its class body is left out, as in a class without the hook"
    k = 2

    def __init__(self) -> None:
        self.items = []

    def __getattr__(self, name: str) -> int:
        return 0

    def get(self, d: int = k) -> int:
        return d


class Hook(Exception):
    def __init_subclass__(cls) -> None:
        print("subclass of Hook:", cls.__name__)


def double(x: int) -> int:
    return 2 * x
