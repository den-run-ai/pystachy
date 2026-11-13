# Fields that hold what their objects start with (constargs, docs/typed-ir.md): one that only
# code which never runs assigns is that value wherever it is read, and one that setattr(),
# copy.copy(), a subclass or a later call assigns is not.
import copy
from dataclasses import dataclass


class Helper:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    def wrap(self, text: str) -> str:
        return self.tag + text + self.tag


class Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.helper: Helper | None = None  # only with_helper() gives one, and nothing calls it
        self.strict = False  # configure() sets it, later
        self.depth = 0  # setattr() sets it
        self.seen = 0

    def with_helper(self, helper: Helper) -> None:
        self.helper = helper

    def configure(self) -> None:
        self.strict = True

    def parse(self) -> str:
        self.seen += 1
        out = self.text
        if self.helper is not None:
            out = self.helper.wrap(out)
        if self.strict:
            out = out.strip()
        if self.depth:
            out = ">" * self.depth + out
        return out


class Tagged(Parser):
    def __init__(self, text: str) -> None:
        Parser.__init__(self, text)
        self.owner: Helper | None = Helper("#")  # a subclass's own, which it always assigns

    def parse(self) -> str:
        out = Parser.parse(self)
        if self.owner is not None:
            out = self.owner.wrap(out)
        return out


@dataclass
class Options:
    verbose: bool = False
    limit: int = 0
    name: str | None = None


def describe(o: Options) -> str:
    out = "options"
    if o.verbose:
        out += " verbose"
    if o.limit:
        out += " limit=" + str(o.limit)
    if o.name is not None:
        out += " name=" + o.name
    return out


def main() -> None:
    p = Parser(" a ")
    print(repr(p.parse()))
    p.configure()
    print(repr(p.parse()))
    setattr(p, "depth", 2)
    print(repr(p.parse()), p.seen)
    q = copy.copy(p)
    q.text = " b "
    print(repr(q.parse()), q.strict, q.depth, q.helper is None)
    t = Tagged("c")
    print(t.parse(), t.helper is None, t.owner is not None)
    print(describe(Options()), "|", describe(Options(limit=3)), "|", describe(Options(True, name="n")))


main()
