# error: 'Half' object does not support the context manager protocol (missed __exit__ method)
class Half:
    def __enter__(self) -> "Half":
        return self


with Half():
    print("not reached")
