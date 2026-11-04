# error: secondary base methods may not use super() or read or write the instance
class Buffer:
    def __init__(self) -> None:
        self.size = 0


class Writer:
    def write(self, size: int) -> None:
        pass

    def flush(self) -> None:
        self.write(self.size)


class Combined(Buffer, Writer):
    pass
