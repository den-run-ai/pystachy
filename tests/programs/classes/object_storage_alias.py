# a value of object holds the object it was given, not a copy: a list or dict stored as object and
# mutated through its typed name shows the change, and 'is' tells it is the same; values that the
# object parameters of templates take (each call's own types) are stored as values of object
class Registry:
    def __init__(self) -> None:
        self.items: list[object] = []
        self.named: dict[str, object] = {}

    def add(self, x: object) -> None:
        self.items.append(x)

    def put(self, k: str, v: object) -> None:
        self.named[k] = v

    def last(self) -> object:
        return self.items[-1]


def store(r: Registry, v: object) -> object:
    r.add(v)
    return v


def main() -> None:
    nums = [1, 2]
    held: object = nums
    nums.append(3)
    print(held, held == [1, 2, 3], held is nums)
    d = {"a": 1}
    box: list[object] = [d, nums]
    d["b"] = 2
    nums.clear()
    print(box, box[0] is d)
    r = Registry()
    r.add(5)
    r.add("five")
    r.add(nums)
    r.add(None)
    r.put("k", 2.5)
    r.put("n", None)
    print(r.items, r.named, r.last())
    nums.append(9)
    print(r.items[2], r.items[2] is nums, store(r, (1, "x")), len(r.items))
    print([store(r, v) for v in [True, 3]], r.items[-1] == 3)
    s: object = "x"
    s = 7
    s = None
    print(s, s is None)
    t: tuple[object, int] = ("first", 2)
    print(t[0], t[1] + 1)
    nested: list[list[object]] = [[1, "a"], [None]]
    nested[1].append(2.5)
    print(nested)
    m: dict[str, list[object]] = {"q": []}
    m["q"].append("z")
    m["q"].append(m["q"][0])
    print(m, m["q"][0] is m["q"][1])
    many: list[object] = []
    for i in range(2000):
        many.append(i if i % 3 == 0 else str(i) if i % 3 == 1 else [i])
    total = 0
    for v in many:
        if isinstance(v, int):
            total += v
    print(len(many), total, many[1997], many[1998], many[1999])


main()
