# error: print_file_no_write.py:9: error: print(file=...) needs a file, or an object with a write() method, not Sink
# an object of a class without write(): CPython raises AttributeError when print() writes to it
class Sink:
    def __init__(self) -> None:
        self.parts: list[str] = []


s = Sink()
print("x", file=s)
