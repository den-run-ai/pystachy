# error: __getitem__ must take 1 argument besides self
class Seq:
    def __getitem__(self) -> int:
        return 0


print(Seq()[0])
