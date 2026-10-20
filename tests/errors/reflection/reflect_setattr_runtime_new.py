# error: reflect_setattr_runtime_new.py:13: error: setattr() of a name only the run time knows is supported for objects whose class closes its names with __slots__
# Without __slots__, a run-time name may add an attribute to the object (#489's later version)
class Options:
    def __init__(self) -> None:
        self.output = ""
        self.level = ""


def parse(argv: list[str]) -> Options:
    ns = Options()
    for arg in argv:
        key, _, val = arg.removeprefix("--").partition("=")
        setattr(ns, key, val)
    return ns


ns = parse(["--output=a.txt", "--level=3"])
print(ns.output, ns.level)
