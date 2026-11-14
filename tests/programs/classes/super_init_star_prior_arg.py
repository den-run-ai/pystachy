class Base:
    def __init__(self, first: "Child" = None, second: "Child" = None) -> None:
        print("base", first is self, second is None)

class Child(Base):
    def method(self) -> None:
        super().__init__(self, *((self := None),))
        print("done")

def invoke(o: Child) -> None:
    try:
        Child.method(o)
    except TypeError as e:
        print("TypeError:", str(e))
    except AttributeError as e:
        print("AttributeError:", str(e))

print("null")
invoke(None)
print("bound")
invoke(Child())
