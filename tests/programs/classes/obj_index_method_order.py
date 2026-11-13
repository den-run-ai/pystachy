# CPython converts a str method's arguments in the parameters' order: a None where a str is
# taken raises before a later argument is asked for its index, but startswith() and endswith()
# check their prefix once their bounds are converted, so an index object's __index__() runs,
# and what it raises comes, first.
class Fails:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def __index__(self) -> int:
        self.log.append("index")
        raise ValueError("index error")


class One:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def __index__(self) -> int:
        self.log.append("index")
        return 1


def maybe(text: str, given: bool) -> str | None:
    return text if given else None


def failing(name: str, s: str, log: list[str]) -> None:
    bad = Fails(log)
    if name == "startswith":
        print(s.startswith(maybe("b", False), bad))
    elif name == "endswith":
        print(s.endswith(maybe("b", False), One(log), bad))
    elif name == "find":
        print(s.find(maybe("b", False), bad))
    elif name == "count":
        print(s.count(maybe("b", False), bad))
    elif name == "index":
        print(s.index(maybe("b", False), bad))
    elif name == "rfind":
        print(s.rfind(maybe("b", False), bad))
    else:
        print(s.replace(maybe("b", False), "x", bad))


def passing(name: str, s: str, log: list[str]) -> None:
    one = One(log)
    if name == "startswith":
        print(s.startswith(maybe("b", False), one))
    elif name == "endswith":
        print(s.endswith(maybe("b", False), one, one))
    elif name == "find":
        print(s.find(maybe("b", False), one))
    elif name == "count":
        print(s.count(maybe("b", False), one))
    elif name == "index":
        print(s.index(maybe("b", False), one))
    elif name == "rfind":
        print(s.rfind(maybe("b", False), one))
    else:
        print(s.replace(maybe("b", False), "x", one))


log: list[str] = []
s = "abcabc"
for name in ["startswith", "endswith", "find", "count", "index", "rfind", "replace"]:
    for fails in [True, False]:
        del log[:]
        try:
            if fails:
                failing(name, s, log)
            else:
                passing(name, s, log)
        except TypeError as e:
            print(name, "TypeError:", e, log)
        except ValueError as e:
            print(name, "ValueError:", e, log)
one = One(log)
print(s.startswith(maybe("bc", True), one), s.find(maybe("c", True), one), s.replace(maybe("b", True), "x", one))
