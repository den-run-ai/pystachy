# A subclass of a class template with an __init__ of its own, annotated, that calls
# super().__init__(...) and overrides a method that the template's methods call, as programs
# subclass threading.Thread (#962).
class Thread:
    def __init__(self, target=None, args=()):
        self._target = target
        self._args = args

    def run(self) -> None:
        if self._target is not None:
            self._target(*self._args)

    def start(self) -> None:
        self.run()


class Worker(Thread):
    def __init__(self, n: int) -> None:
        super().__init__()
        self.n = n

    def run(self) -> None:
        print("worker", self.n)


def hello(a: int, b: str) -> None:
    print("hello", a, b)


Thread(hello, (1, "x")).start()
Worker(3).start()
