# print(file=obj) where obj is an object of the program's classes with a write() method: each piece
# is passed to obj.write(), one call each, as CPython makes them: str() of each argument just
# before it is written, sep between them, end last, then obj.flush() if flush is true
class Log:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def write(self, s: str) -> int:
        self.calls.append(s)
        return len(s)

    def flush(self) -> None:
        self.calls.append("<flush>")


class Noisy:
    def __init__(self, name: str, log: Log) -> None:
        self.name = name
        self.log = log

    def __str__(self) -> str:
        self.log.calls.append(f"<str {self.name}>")
        return self.name


log = Log()
print("a", 1, 2.5, None, True, [1, 2], (3, "x"), file=log)
print(file=log)
print("x", "y", sep="--", end="!\n", file=log)
print("z", end="", flush=True, file=log)
print("w", flush=False, file=log)
print("v", sep=None, end=None, file=log)
print(Noisy("n1", log), Noisy("n2", log), sep="|", file=log)
for c in log.calls:
    print(repr(c))


class Upper:
    # a class template: write() is compiled for the str it is given
    def __init__(self, prefix):
        self.prefix = prefix
        self.out = ""

    def write(self, s):
        self.out += self.prefix + s.upper()


u = Upper("> ")
print("hello", "world", file=u)
print("again", file=u)
print(repr(u.out))


class Failing:
    def __init__(self) -> None:
        self.n = 0

    def write(self, s: str) -> None:
        self.n += 1
        if self.n == 3:
            raise OSError("disk full")


f = Failing()
try:
    print("one", "two", "three", file=f)
except OSError as e:
    print("OSError:", e, f.n)
import sys
print("to stdout", file=sys.stdout)
print("to stdout", file=None)


class Sink:
    # write() and no flush(): CPython looks flush() up only where flush is true
    def __init__(self) -> None:
        self.out = ""

    def write(self, s: str) -> None:
        self.out += s


sink = Sink()
print("ok", file=sink, flush=False)
print("ok", 2, file=sink, flush=0)
print("ok", 3, file=sink, flush=len(sys.argv) > 5)
try:
    print("now", file=sink, flush=True)
except AttributeError as e:
    print("AttributeError:", e)
print(repr(sink.out))
