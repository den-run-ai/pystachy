# A class template's fields given None by arguments: each specialization's own type,
# which a later store gives (b.v = 5), also after a method has read it.
class Box:
    def __init__(self, v, tag=None):
        self.v = v
        self.tag = tag

    def show(self) -> str:
        return f"{self.v!r} {self.tag!r}"


b = Box(None)
print(b.show(), Box(1).show(), Box("s", "t").show())
print(b.v is None, b.tag)
b.v = 5
print(b.v, b.show())
