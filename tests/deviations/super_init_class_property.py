# An unbound super initializer cannot validate a replacement receiver through a
# custom __class__. The bound initializer stays supported, and None needs no lookup.
class E(Exception):
    pass


class Proxy:
    @property
    def __class__(self) -> type[BaseException]:
        print("class property")
        return E


class ChildProxy(Proxy):
    pass


class Base:
    def __init__(self, cls: type[BaseException], proxy: ChildProxy) -> None:
        print("base initialized")


class Child(Base):
    def proxy(self) -> None:
        super().__init__(E, ChildProxy())
        print("proxy initialized")

    def absent(self, proxy: ChildProxy) -> None:
        super().__init__(E, proxy)
        print("absent initialized")


value: Child | None = None
try:
    Child.proxy(value)
except NotImplementedError as error:
    print(str(error))
Child.absent(value, None)
Child.proxy(Child(E, ChildProxy()))
