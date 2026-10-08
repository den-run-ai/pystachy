class V:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def __add__(self, o: "V") -> "V":
        return V(self.x + o.x, self.y + o.y)

    def __mul__(self, k: int) -> "V":
        return V(self.x * k, self.y * k)

    def __eq__(self, o: "V") -> bool:
        return self.x == o.x and self.y == o.y

    def __lt__(self, o: "V") -> bool:
        return self.x * self.x + self.y * self.y < o.x * o.x + o.y * o.y

    def __len__(self) -> int:
        return 2

    def __repr__(self) -> str:
        return f"V({self.x}, {self.y})"


a = V(1, 2) + V(3, 4) * 2
print(a, a == V(7, 10), a != V(7, 10), V(1, 1) < a, len(a))
c = "b"
print(c in ("a", "b"), 3 not in (1, 2), "z" in ("x", "y"))
for x, y in zip([1, 2, 3], "abcd"):
    print(x, y, end=" ")
print()
for ch in reversed("xyz"):
    print(ch, end="")
print()
for i, (k, v) in enumerate({"p": 1, "q": 2}.items()):
    print(i, k, v)
for p, q, r in zip([1, 2], [3.5, 4.5], ["u", "v"]):
    print(p, q, r)
