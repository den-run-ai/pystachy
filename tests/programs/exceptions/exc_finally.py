# finally blocks on every way out: the end, an exception, return, break and continue, and those
# of the finally block itself; return evaluates its value before the finally block runs


def ret_through(n: int) -> int:
    try:
        print("try", n)
        return n * 2
    finally:
        print("finally", n)


def ret_override(n: int) -> int:
    try:
        return n
    finally:
        if n > 0:
            return -n


def value_first() -> int:
    x = 1
    try:
        return x
    finally:
        x = 5
        print("x set to", x)


def discard(n: int) -> str:
    # a return in a finally block drops the exception on its way
    try:
        if n > 1:
            raise ValueError("dropped")
        return "body"
    finally:
        if n > 2:
            return "finally"


def nested(n: int) -> int:
    total = 0
    try:
        try:
            total += 1
            if n == 1:
                raise KeyError(n)
            if n == 2:
                return total
        finally:
            total += 10
            print("inner finally", total)
    except KeyError as e:
        print("caught", repr(e), total)
        total += 100
    finally:
        print("outer finally", total)
    return total


def loops() -> None:
    for i in range(5):
        try:
            if i == 1:
                continue
            if i == 3:
                break
            print("body", i)
        finally:
            print("finally", i)
    print("after for")
    i = 0
    while True:
        i += 1
        try:
            try:
                if i % 2 == 0:
                    raise ValueError(i)
            except ValueError as e:
                print("even", e)
                continue
            if i > 4:
                break
        finally:
            print("w finally", i)
    print("after while", i)


def break_in_finally() -> int:
    n = 0
    for i in range(3):
        try:
            n += 1
            raise IndexError(i)
        finally:
            break
    return n


def continue_in_finally() -> list[int]:
    out: list[int] = []
    for i in range(4):
        try:
            if i % 2 == 1:
                raise RuntimeError("odd")
            out.append(i)
        finally:
            continue
    return out


def else_block(n: int) -> str:
    r = ""
    try:
        if n < 0:
            raise ValueError("neg")
        r += "try "
    except ValueError:
        r += "except "
    else:
        r += "else "
    finally:
        r += "finally"
    return r


print(ret_through(3))
print(ret_override(0), ret_override(4))
print(value_first())
print(discard(1), discard(3))
try:
    print(discard(2))
except ValueError as e:
    print("escaped", e)
for k in range(4):
    print("nested", k, nested(k))
loops()
print(break_in_finally())
print(continue_in_finally())
print(else_block(1), "|", else_block(-1))
