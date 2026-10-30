# pystachy: dynamic-any
# Integer methods, formatting and index protocols must inspect a wide numeric payload.
from typing import Any
from any_wide_values import make

wide: Any = make(70)
negative: Any = -wide
print(wide.bit_length(), wide.bit_count(), negative.bit_length(), negative.bit_count())
print(f"{wide:d}", f"{negative:+d}", f"{wide:#x}", f"{negative:#b}")
print(format(wide, "025d"), format(negative, "_d"))
values: Any = [0, 1, 2, 3]
text: Any = "abcd"
pair: Any = (0, 1, 2, 3)
for seq in [values, text, pair]:
    try:
        print(seq[wide])
    except IndexError:
        print("large positive index")
    try:
        print(seq[negative])
    except IndexError:
        print("large negative index")
    print(seq[negative:wide], seq[::wide], seq[::negative])
try:
    values[wide] = 9
except IndexError:
    print("large store index")
try:
    del values[negative]
except IndexError:
    print("large delete index")
print(values)


def repeat(seq: Any, count: Any) -> None:
    try:
        print(seq * count)
    except OverflowError:
        print("repeat overflow")


repeat("", wide)
repeat("", negative)
repeat([], wide)
repeat([], negative)
repeat((), wide)
repeat((), negative)


class Index:
    def __init__(self, name: str, value: Any) -> None:
        self.name = name
        self.value = value

    def __index__(self) -> Any:
        print("index", self.name)
        return self.value


lo: Any = Index("start", negative)
hi: Any = Index("stop", wide)
step: Any = Index("step", wide)
print(values[lo:hi:step])
step = Index("zero", 0)
try:
    print(values[lo:hi:step])
except ValueError:
    print("zero step")


class BadInt:
    def __int__(self) -> Any:
        print("bad int")
        return "bad"

    def __index__(self) -> Any:
        print("unwanted fallback")
        return 1


bad: Any = BadInt()
try:
    print(int(bad))
except TypeError:
    print("bad int type")
bad = Index("bad", 1.5)
try:
    print(values[bad])
except TypeError:
    print("bad index type")
