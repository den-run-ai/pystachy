# contextlib.ExitStack: managers of different classes, callbacks, suppression and pop_all().
from contextlib import ExitStack


class Entry:
    def __init__(self, log: list[str], name: str) -> None:
        self.log = log
        self.name = name

    def __enter__(self) -> "Entry":
        self.log.append("enter " + self.name)
        return self

    def __exit__(self, a: type[BaseException] | None, b: BaseException | None, c: object) -> bool:
        self.log.append("exit " + self.name + " " + str(a is None))
        return False


class Swallow:
    def __enter__(self) -> int:
        return 7

    def __exit__(self, a, b, c):
        print("swallow sees", b)
        return True


def note(log: list[str], text: str, n: int = 1) -> None:
    log.append(text * n)


def run(names: list[str]) -> list[str]:
    log: list[str] = []
    with ExitStack() as stack:
        for name in names:
            e = stack.enter_context(Entry(log, name))
            log.append("got " + e.name)
        stack.callback(note, log, "cb", n=2)
        log.append("body")
    return log


def run2() -> list[str]:
    log: list[str] = []
    try:
        with ExitStack() as stack:
            stack.enter_context(Entry(log, "outer"))
            print(stack.enter_context(Swallow()))
            stack.enter_context(Entry(log, "inner"))
            raise ValueError("boom")
    except ValueError as e:
        log.append("escaped " + str(e))
    log.append("after")
    return log


print(run(["a", "b", "c"]))
print(run2())
s = ExitStack()
log3: list[str] = []
s.enter_context(Entry(log3, "x"))
t = s.pop_all()
s.close()
print(log3)
t.close()
print(log3)
