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
        pass

class Child(Base):
    def method(self, proxy: ChildProxy) -> None:
        super().__init__(E, proxy)
        print("initialized")

def invoke(receiver: Child) -> None:
    Child.method(receiver, ChildProxy())

invoke(Child(E, ChildProxy()))
