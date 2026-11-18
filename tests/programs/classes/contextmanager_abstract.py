# An abstract method that is a @contextmanager, as mypy's TypeCheckerSharedApi.checking_await_set:
# its body only raises, which CPython's helper runs where the method is called, and an override
# is a generator. Either order of the decorators, and their qualified names.
import abc
import contextlib
from abc import abstractmethod
from contextlib import contextmanager
from typing import Iterator


class Api:
    @abstractmethod
    @contextmanager
    def scope(self) -> Iterator[None]:
        """Enter a scope."""
        raise NotImplementedError

    @contextlib.contextmanager
    @abc.abstractmethod
    def named(self, name: str, depth: int = 1) -> Iterator[None]:
        raise NotImplementedError("named " + name)


class Real(Api):
    def __init__(self) -> None:
        self.depth = 0
        self.log: list[str] = []

    @contextmanager
    def scope(self) -> Iterator[None]:
        self.depth += 1
        try:
            yield
        finally:
            self.depth -= 1

    @contextmanager
    def named(self, name: str, depth: int = 1) -> Iterator[None]:
        self.log.append("enter " + name + str(depth))
        yield
        self.log.append("exit " + name)


class Partial(Api):
    @contextmanager
    def scope(self) -> Iterator[None]:
        print("partial scope")
        yield


def run(a: Api) -> str:
    with a.scope():
        with a.named("n", depth=2):
            return "in"


def make(a: Api) -> str:
    try:
        a.named("x")
        return "made"
    except NotImplementedError as e:
        return "the call raised: " + str(e)


r = Real()
print(run(r), r.depth, r.log)
print(make(r), make(Partial()), make(Api()))
try:
    with Api().scope():
        print("unreachable")
except NotImplementedError:
    print("abstract scope")
try:
    print(run(Partial()))
except NotImplementedError as e:
    print("partial named:", e)
