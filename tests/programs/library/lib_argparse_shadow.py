import argparse


class LocalParser:
    def parse_args(self) -> int:
        return 42


class Factory:
    def ArgumentParser(self) -> LocalParser:
        return LocalParser()


def local(argparse: Factory) -> None:
    p = argparse.ArgumentParser()
    print(p.parse_args())


local(Factory())

# The method owns its 'p' parameter even though the module also binds 'p'.
class UsesLocal:
    def value(self, p: LocalParser) -> int:
        return p.parse_args()


p = argparse.ArgumentParser()
p.add_argument("value", type=int)
print(UsesLocal().value(LocalParser()), p.parse_args(["3"]).value)


class Other:
    def format_usage(self) -> str:
        return "the other parser"


def comprehension() -> None:
    p = argparse.ArgumentParser(prog="local", add_help=False)
    print([p.format_usage() for p in [Other()]])
    print(p.format_usage(), end="")


comprehension()
