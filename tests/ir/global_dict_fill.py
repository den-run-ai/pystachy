# Global dicts created empty in module code and filled only by functions, then read: their
# key kind is known only once the function that fills them is compiled.
REG = {}
IDS = {}


def add(k: str) -> None:
    REG[k] = 1


def number(i: int, name: str) -> None:
    IDS[i] = name


def show() -> None:
    print(REG, len(REG), "a" in REG)
    for i in IDS:
        print(i, IDS[i])


add("a")
add("b")
number(7, "seven")
number(3, "three")
show()
