# repr() and str() of containers holding exceptions run the __repr__ of an exception class whose
# object an exception is: what that raises is caught by the try statement around (the runtime's
# repr is a call that may raise there, an invoke).
class E(Exception):
    def __repr__(self) -> str:
        raise KeyError("repr fail")


def shown(e: Exception) -> str:
    try:
        return f"{[e]}"
    except KeyError:
        return "caught in f-string"


try:
    raise E()
except Exception as e:
    try:
        print([e])
    except KeyError:
        print("caught")
    try:
        print(str({1: e}))
    except KeyError as k:
        print("caught", k)
    try:
        print((e, 1))
    except KeyError:
        print("caught tuple")
    print(shown(e))
    print(shown(ValueError("v")))
