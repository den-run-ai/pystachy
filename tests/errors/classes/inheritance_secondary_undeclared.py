# error: secondary base methods may not use super() or read or write the instance
class Buffer:
    def write(self, value: int) -> None:
        print(value)


class Writer:
    def flush(self) -> None:
        self.write(1)


class Combined(Buffer, Writer):
    pass
