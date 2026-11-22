# Exception classes nested in a class body: raised and caught as Outer.Error, with CPython's
# __name__ (repr(), type(e).__name__), __qualname__ (Outer.Error, str(type(e))) and __module__,
# through the class and through an exception object.
class Client:
    class Error(Exception):
        pass

    class Timeout(Error):
        def __init__(self, after: int) -> None:
            super().__init__(f"after {after}s")
            self.after = after

    def fetch(self, n: int) -> str:
        if n > 2:
            raise Client.Timeout(n)
        if n < 0:
            raise self.Error("negative")
        return "ok"


c = Client()
for n in [1, 3, -1]:
    try:
        print(c.fetch(n))
    except Client.Timeout as e:
        print("timeout", e.after, repr(e), type(e).__name__, type(e).__qualname__, type(e).__module__, type(e))
    except Client.Error as e:
        print("error", e, repr(e), type(e).__qualname__, str(type(e)))
print(Client.Error.__name__, Client.Error.__qualname__, Client.Error.__module__, issubclass(Client.Timeout, Client.Error))
