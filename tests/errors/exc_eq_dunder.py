# error: == between exceptions is not supported where an exception class defines __eq__ (E does)
class E(Exception):
    def __eq__(self, o: "E") -> bool:
        return True


try:
    raise E("a")
except Exception as e:
    try:
        raise E("b")
    except Exception as f:
        print(e == f)
