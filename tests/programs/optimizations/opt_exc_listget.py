# listget across exception edges (docs/typed-ir.md 7.1): a for loop over a list reads its items
# without a bounds check after the test of each pass; a handler of the same function that
# shortens the list goes on to the next pass (or after the loop), whose test sees the new length.


def shrink_in_handler(xs: list[int]) -> list[int]:
    out: list[int] = []
    for x in xs:
        try:
            out.append(100 // x)
        except ZeroDivisionError:
            xs.pop()
            xs.pop()
    return out


def clear_and_continue(xs: list[str]) -> int:
    n = 0
    for s in xs:
        try:
            n += int(s)
        except ValueError:
            xs.clear()
            continue
        n += 1000
    return n


def zip_shrink(a: list[int], b: list[int]) -> list[int]:
    out: list[int] = []
    for x, y in zip(a, b):
        try:
            out.append(x // y)
        except ZeroDivisionError:
            del b[len(b) - 1]
            out.append(-1)
    return out


def enumerate_shrink(xs: list[str]) -> list[str]:
    out: list[str] = []
    for i, s in enumerate(xs):
        try:
            if s == "boom":
                raise KeyError(s)
            out.append(f"{i}:{s}")
        except KeyError:
            while len(xs) > i:
                xs.pop()
    return out


def around_loop(xs: list[int]) -> int:
    # (an exception leaves the loop; the handler shortens the list and loops over it again)
    total = 0
    try:
        for x in xs:
            total += 10 // x
    except ZeroDivisionError:
        while len(xs) > 2:
            xs.pop()
        for x in xs:
            total += x
    return total


def finally_pops(xs: list[int]) -> list[int]:
    out: list[int] = []
    for x in xs:
        try:
            if x < 0:
                continue
            out.append(x)
        finally:
            if x == 0:
                xs.pop()
    return out


def nested(xss: list[list[int]]) -> int:
    t = 0
    for xs in xss:
        for x in xs:
            try:
                t += 12 // x
            except ZeroDivisionError:
                xs.clear()
                xss.pop()
    return t


print(shrink_in_handler([5, 0, 4, 2, 1, 7]), shrink_in_handler([1, 2]), shrink_in_handler([0, 1]))
print(clear_and_continue(["1", "2", "x", "4"]), clear_and_continue(["7"]))
print(zip_shrink([1, 2, 3, 4], [1, 0, 1, 1]), zip_shrink([5], [0]))
print(enumerate_shrink(["a", "b", "boom", "c"]), enumerate_shrink(["boom"]))
xs = [5, 2, 0, 3, 4]
print(around_loop(xs), xs)
print(finally_pops([1, 0, 2, -1, 3, 4]), finally_pops([0, 0, 0]))
print(nested([[1, 2], [3, 0, 4], [6], [12]]))
