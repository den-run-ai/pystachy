# A class's method named open binds the name in the class's namespace only: the open() its
# methods call is the builtin, which makes a binary file of a binary mode
import os
import tempfile


class Archive:
    def __init__(self, path: str) -> None:
        self.path = path

    def open(self) -> bytes:
        with open(self.path, "rb") as f:
            return f.read()

    def save(self, data: bytes) -> int:
        return open(self.path, "wb").write(data)


d = tempfile.mkdtemp()
a = Archive(os.path.join(d, "a.bin"))
print(a.save(b"\x00archive\xff"))
print(a.open())
