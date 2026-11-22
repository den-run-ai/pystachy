# A flag that chooses str or bytes, in a function and in a method of a class that takes part in no
# inheritance: each call's literal compiles its own instance.
def read(text: str, binary: bool = False):
    if binary:
        return text.encode()
    return text


class Reader:
    def __init__(self, text: str) -> None:
        self.text = text

    def get(self, binary: bool = False):
        if binary:
            return self.text.encode()
        return self.text


print(read("a"), read("b", binary=True), read("c", True)[0])
r = Reader("xy")
print(r.get().upper(), r.get(binary=True)[1], len(r.get(True)))
