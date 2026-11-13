class Lex:
    def __init__(self, src: bytes):
        self.src = src
        self.pos = 0
        self.count = 0

    def run(self) -> int:
        src = self.src
        n = len(src)
        while self.pos < n:
            c = src[self.pos]
            if c == 32:
                self.count += 1
            self.pos += 1
        return self.count


def total(data: bytes, out: list[int]) -> None:
    for i in range(len(data)):
        out[i & 7] += data[i]


import sys
d = open(sys.argv[1], "rb").read()
print(Lex(d).run())
o = [0] * 8
total(d, o)
print(o[0])
