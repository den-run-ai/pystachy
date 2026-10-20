# An empty global container that only functions fill, read by code compiled before them:
# such a function is compiled first, and its fill gives the container its type. Also fills
# through setdefault(k, []).append(v) and setdefault(k, {})[k2] = v, through a method, with
# values a function computes, before any fill runs, and in a function that reads the global
# before it.
REG = {}


def register(name: str, v: int) -> None:
    REG[name] = v


register("a", 1)
print(REG)

ITEMS = []


def add(x: int) -> None:
    ITEMS.append(x * 2)


print(len(ITEMS), ITEMS == [], ITEMS)
add(1)
add(5)
print(ITEMS)

LISTS = {}


def put(name: str, v: int) -> None:
    LISTS.setdefault(name, []).append(v)


put("a", 1)
put("a", 2)
print(LISTS)

GROUPS = {}


def group(k: str, sub: str, v: float) -> None:
    GROUPS.setdefault(k, {})[sub] = v


group("x", "y", 1.5)
group("x", "z", 2.0)
print(GROUPS)

TAGS = {}


class Tagger:
    def __init__(self, tag: str):
        self.tag = tag

    def add(self, k: str) -> None:
        TAGS[k] = self.tag


print(TAGS)
Tagger("t").add("x")
print(TAGS)

PARSED = {}


def load(line: str) -> None:
    parts = line.split("=")
    PARSED[parts[0]] = int(parts[1])


load("a=1")
load("b=22")
print(PARSED, sum(PARSED.values()))

SCALED = {}


def show() -> None:
    print("show", SCALED)


def scale(k: str) -> None:
    SCALED[k] = FACTOR * 2


print(SCALED)
FACTOR = 1.5
scale("a")
show()

COUNTS = {}


def bump(k: int) -> None:
    COUNTS[k] = COUNTS.get(k, 0) + 1


for i in [1, 2, 1]:
    bump(i)
print(COUNTS)

SEEN = []


def remember(x: str) -> bool:
    if x in SEEN:
        return False
    SEEN.append(x)
    return True


print(remember("a"), remember("b"), remember("a"), SEEN)

STACK = []


def push(x: int) -> None:
    STACK.append(x)


def pop() -> int:
    return STACK.pop()


push(3)
push(4)
print(pop(), STACK)

TABLE = {}


def setup(k: str) -> None:
    global TABLE
    TABLE[k] = [len(k)]


def reset() -> None:
    global TABLE
    TABLE = {}


setup("ab")
reset()
setup("xyz")
print(TABLE)

NEVER = {}


def never(k: str) -> None:
    NEVER[k] = 1.0


print(NEVER, len(NEVER))

ROOT = {}
ROOT.setdefault("a", []).append(1)
ROOT.setdefault("b", []).insert(0, 3)
print(ROOT)
