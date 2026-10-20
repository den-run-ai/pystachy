# error: == between an exception and None is not supported where an exception class defines __eq__ (E does)
class E(Exception):
    def __eq__(self, o: "E") -> bool:
        return True


try:
    raise E("a")
except Exception as e:
    print(e == None)  # (CPython calls E.__eq__: True)
