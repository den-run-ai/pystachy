from __future__ import annotations

# The subset has no dict, but one is easy to write in it: open addressing, str -> int.


class Map:
    keys: list[str]
    vals: list[int]
    used: list[bool]
    size: int

    def __init__(self) -> None:
        self.keys = [""] * 8
        self.vals = [0] * 8
        self.used = [False] * 8
        self.size = 0

    def slot(self, key: str) -> int:
        h = 5381
        for i in range(len(key)):
            h = (h * 33 + ord(key[i])) % 4294967296
        i = h % len(self.keys)
        while self.used[i] and self.keys[i] != key:
            i = (i + 1) % len(self.keys)
        return i

    def set(self, key: str, val: int) -> None:
        if self.size * 2 >= len(self.keys):
            self.grow()
        i = self.slot(key)
        if not self.used[i]:
            self.used[i] = True
            self.keys[i] = key
            self.size += 1
        self.vals[i] = val

    def get(self, key: str, default: int) -> int:
        i = self.slot(key)
        if self.used[i]:
            return self.vals[i]
        return default

    def grow(self) -> None:
        keys = self.keys
        vals = self.vals
        used = self.used
        n = len(keys) * 2
        self.keys = [""] * n
        self.vals = [0] * n
        self.used = [False] * n
        self.size = 0
        for i in range(len(keys)):
            if used[i]:
                self.set(keys[i], vals[i])


def split(s: str) -> list[str]:
    out: list[str] = []
    word = ""
    for ch in s:
        if ch == " " or ch == "\n":
            if len(word) > 0:
                out.append(word)
            word = ""
        else:
            word = word + ch
    if len(word) > 0:
        out.append(word)
    return out


text = """the quick brown fox jumps over the lazy dog
the dog barks and the fox runs away over the hill"""
counts = Map()
for w in split(text):
    counts.set(w, counts.get(w, 0) + 1)
print(counts.size, counts.get("the", 0), counts.get("fox", 0), counts.get("over", 0), counts.get("cat", -1))
m = Map()
for i in range(5000):
    m.set("k" + str(i), i * i)
total = 0
for i in range(5000):
    total += m.get("k" + str(i), -1)
print(m.size, len(m.keys), total, m.get("k4999", 0), m.get("missing", -1))
