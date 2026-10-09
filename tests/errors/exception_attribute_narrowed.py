# error: the attributes of an exception (e.n) are not supported; str(e) and repr(e) are (to read the fields of E, catch it by its class: except E as e)
class E(Exception):
    def __init__(self, n: int):
        super().__init__(n)
        self.n = n


try:
    raise E(1)
except Exception as e:
    if isinstance(e, E):
        print(e.n)
