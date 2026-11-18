# A class in a hierarchy takes, as a parameter of its __init__, an object of a class that keeps
# class-template objects (defaultdict, Counter, deque) in annotated fields. Such a class is no
# template where a hierarchy's __init__ names it, also through another class's __init__, so the
# hierarchy is none either (mypy's checkers take its Errors and Options so).
from collections import Counter, defaultdict, deque


class Options:
    def __init__(self, strict: bool) -> None:
        self.strict = strict
        self.flags: Counter[str] = Counter()
        self.flags["strict"] += 1 if strict else 0


class Errors:
    recorded: defaultdict[str, list[str]]

    def __init__(self, options: Options) -> None:
        self.options = options
        self.recorded = defaultdict(list)
        self.order: deque[str] = deque()
        self.count = 0

    def add(self, path: str, message: str) -> None:
        self.recorded[path].append(message)
        self.order.append(path)
        self.count += 1

    def messages(self, path: str) -> list[str]:
        return self.recorded[path] if path in self.recorded else []


class Visitor:
    def __init__(self, errors: Errors, name: str = "visitor") -> None:
        self.errors = errors
        self.name = name

    def visit(self, node: str) -> None:
        self.errors.add(self.name, node)


class Checker(Visitor):
    def __init__(self, errors: Errors, options: Options) -> None:
        super().__init__(errors, "checker")
        self.options = options

    def visit(self, node: str) -> None:
        if self.options.strict:
            self.errors.add(self.name, "strict " + node)
        super().visit(node)


class Quiet(Visitor):
    def visit(self, node: str) -> None:
        pass


def run(visitors: list[Visitor], nodes: list[str]) -> None:
    for v in visitors:
        for n in nodes:
            v.visit(n)


options = Options(True)
errors = Errors(options)
other = Errors(Options(False))
run([Visitor(errors), Checker(errors, options), Quiet(other), Checker(other, other.options)], ["a", "b"])
print(errors.count, errors.messages("visitor"), errors.messages("checker"), list(errors.order))
print(other.count, other.messages("checker"), other.messages("quiet"), list(other.order))
print(options.flags["strict"], other.options.flags["strict"], isinstance(errors, Errors), type(errors).__name__)
extra = Errors(options)
extra.add("p", "q")
print(extra.count, errors.count, extra.messages("p"), [e.count for e in [errors, other, extra]])
