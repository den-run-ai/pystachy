# A base and a derived exception class can hold the same object. Stores through either
# view must invalidate the key or dict field that dictfuse's canonicalization last read.
class KeyBase(Exception):
    def __init__(self, key: int):
        self.key = key


class KeyChild(KeyBase):
    def __init__(self, key: int):
        super().__init__(key)


class KeyGrandchild(KeyChild):
    def __init__(self, key: int):
        super().__init__(key)


class KeySibling(KeyBase):
    def __init__(self, key: int):
        super().__init__(key)


def read_base(a: KeyBase, b: KeyChild, d: dict[int, int]) -> int:
    before = d[a.key]
    b.key = 2
    return d[a.key]


def read_child(a: KeyChild, b: KeyBase, d: dict[int, int]) -> int:
    before = d[a.key]
    b.key = 2
    return d[a.key]


def write_base(a: KeyBase, b: KeyGrandchild, d: dict[int, int]) -> None:
    before = d[a.key]
    b.key = 2
    d[a.key] = 99


def missing(a: KeyBase, b: KeyChild, d: dict[int, int]) -> None:
    before = d[a.key]
    b.key = 2
    try:
        print(d[a.key])
    except KeyError as e:
        print("KeyError", e)


def siblings(a: KeyChild, b: KeySibling, d: dict[int, int]) -> int:
    before = d[a.key]
    b.key = 2
    return d[a.key]


class DictBase(Exception):
    def __init__(self):
        self.values: dict[int, int] = {1: 10}


class DictChild(DictBase):
    def __init__(self):
        super().__init__()


def replace_dict(a: DictBase, b: DictChild, replacement: dict[int, int]) -> int:
    before = a.values[1]
    b.values = replacement
    return a.values[1]


child = KeyChild(1)
print(read_base(child, child, {1: 10, 2: 20}))
child = KeyChild(1)
print(read_child(child, child, {1: 10, 2: 20}))
grandchild = KeyGrandchild(1)
print(read_base(grandchild, grandchild, {1: 10, 2: 20}))
grandchild = KeyGrandchild(1)
values = {1: 10, 2: 20}
write_base(grandchild, grandchild, values)
print(values)
child = KeyChild(1)
missing(child, child, {1: 10})
print(siblings(KeyChild(1), KeySibling(1), {1: 10, 2: 20}))
child_dict = DictChild()
print(replace_dict(child_dict, child_dict, {9: 90, 1: 20}))
