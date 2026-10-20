from io import StringIO
from typing import TextIO
import os


class Holder:
    def __init__(self, stream: TextIO | StringIO) -> None:
        self.stream: TextIO | StringIO = stream


def consume(stream: TextIO | StringIO) -> str:
    return stream.read(1)


path = "/tmp/pystachy-reference-union-" + str(os.getpid()) + ".txt"
try:
    with open(path, "w") as output:
        output.write("disk")
    memory = StringIO("memory")
    disk = open(path)
    items: list[TextIO | StringIO] = [memory, disk, memory, disk]
    for item in items:
        holder = Holder(item)
        print(consume(holder.stream))
    print(memory.read(2), disk.read(2))
    for item in items:
        item.close()
finally:
    os.remove(path)
