# pystachy: python-int
# Importing the dynamic helper activates identity tracking for these promoting slots.
# Copying or storing an out-of-int64 value must not narrow it merely to make a companion.
import intidentity
import plaincells


class Box:
    def __init__(self, value: int) -> None:
        self.value = value


def passed(value: int) -> int:
    alias = value
    return alias


GLOBAL = int("1180591620717411303424")
COPY = GLOBAL
LEFT = RIGHT = int("1180591620717411303424")


def optional_cell(value: int | None) -> None:
    def read() -> int | None:
        if value is not None:
            return value
        return None

    def clear() -> None:
        nonlocal value
        value = None

    if value is not None:
        print("wide shared narrowed", value)
        intidentity.churn()
        print("wide captured narrowed", read())
    clear()
    print("wide optional cell cleared", read() is None)


def run() -> None:
    value = GLOBAL
    alias = value
    left = right = value
    box = Box(value)
    box.value = copied = int("1180591620717411303424")
    maybe: int | None = value

    def read() -> int:
        return value

    def default(first: int = value, second: int = -value) -> None:
        print("wide defaults", first, second)

    intidentity.churn()
    print("wide global/copy", GLOBAL, COPY, alias)
    print("wide chained copy", LEFT, RIGHT, left, right)
    print("wide parameter/return", passed(value))
    print("wide field/optional", box.value, maybe)
    print("wide field/local chain", box.value, copied)
    print("wide closure", read())
    default()
    # A wide slot may later hold an ordinary value whose identity must be retained.
    box.value = int("14000")
    intidentity.keep(box.value)
    intidentity.churn()
    intidentity.keep(box.value)
    intidentity.check("wide field replaced")
    maybe = None
    print("wide optional cleared", maybe)
    optional_cell(GLOBAL)
    optional_cell(None)
    reader = plaincells.capture_pair(GLOBAL, -GLOBAL)
    intidentity.churn()
    reader()
