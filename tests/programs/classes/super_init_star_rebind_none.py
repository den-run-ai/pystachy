
class C(Exception):
    def method(self) -> None:
        super().__init__(*((self := None),))
        print("done")


def invoke(o: C) -> None:
    try:
        C.method(o)
    except TypeError as e:
        print("TypeError:", str(e))
    except ValueError as e:
        print("ValueError:", str(e))
    except AttributeError as e:
        print("AttributeError:", str(e))

print("null")
invoke(None)
print("bound")
invoke(C("original"))
