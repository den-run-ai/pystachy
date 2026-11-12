# IndexError of str and list indexing and of list.pop() inside try and with statements, whose
# bounds are checked in the function itself.
def get(s: str, i: int) -> str | None:
    try:
        return s[i]
    except IndexError:
        return None


def last(xs: list[str]) -> str:
    try:
        return xs[-1]
    except IndexError as e:
        return "<" + str(e) + ">"


def at(xs: list[int], i: int) -> int:
    try:
        return xs[i]
    except IndexError:
        return -999


def msg(s: str, i: int) -> str:
    try:
        return s[i]
    except IndexError as e:
        return str(e)


def nested(s: str) -> str:
    out = ""
    try:
        try:
            out += s[5]
        finally:
            out += "f"
    except IndexError:
        out += "x"
    with open("/dev/null") as f:
        try:
            out += s[0]
            out += s[-9]
        except IndexError:
            out += "y"
    return out


print([get("héllo", i) for i in range(-7, 7)])
print(last([]), last(["a", "b"]), [at([10, 20, 30], i) for i in range(-5, 5)])
print(msg("ab", 2), msg("ab", -3), msg("ab", -2), nested("abcdefgh"), nested("ab"), nested(""))
try:
    print("abc"[7])
except IndexError as e:
    print("module-level", e)
class Ctx:
    def __init__(self) -> None:
        self.context: list[str] = []
        self.current: str | None = None
        self.empty = True

    def set(self, v: str) -> None:
        self.context.append(v)
        self.current = v
        self.empty = False

    def reset(self) -> None:
        try:
            self.context.pop()
            self.current = self.context[-1]
        except IndexError:
            self.current = None
            self.empty = True


def pops(xs: list[int], i: int) -> str:
    try:
        return str(xs.pop(i)) + ":" + str(xs)
    except IndexError as e:
        return str(e)


c = Ctx()
c.reset()
print(c.current, c.empty)
c.set("a")
c.set("b")
c.reset()
print(c.current, c.empty)
c.reset()
print(c.current, c.empty)
print(pops([], -1), pops([1, 2, 3], 0), pops([1, 2, 3], -1), pops([1, 2, 3], 3), pops([1, 2, 3], -4), pops([1], -1))
nums: list[float] = [1.5]
try:
    print(nums.pop(), nums.pop())
except IndexError as e:
    print("empty:", e)
