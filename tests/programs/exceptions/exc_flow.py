# definite assignment through try statements, locals the body assigns that a handler reads (at
# -O2 too), the name an except clause binds (unbound after it), templates and modules that raise
from mods.parsing import WIDTH, number, safe


def assigned_in_body(s: str) -> str:
    count = 0
    stage = "start"
    try:
        stage = "parse"
        count += 1
        n = int(s)
        stage = "done"
        count += 1
        return f"{n} {stage} {count}"
    except ValueError:
        return f"failed at {stage} after {count}"


def maybe_bound(s: str) -> None:
    try:
        v = int(s)
    except ValueError:
        pass
    try:
        print("v is", v)
    except UnboundLocalError as e:
        print("unbound:", e)


def name_unbound() -> None:
    try:
        raise KeyError("k")
    except KeyError as err:
        print("inside", repr(err))
    try:
        print(err)
    except NameError as e:
        print("after:", e)


def first(xs, default):
    # a template's function with a try
    try:
        return xs[0]
    except IndexError:
        return default


def loop_sum(words: list[str]) -> int:
    total = 0
    for w in words:
        try:
            total += number(w)
        except ValueError:
            continue
        except OverflowError as e:
            print("too big:", e)
            break
    return total


print(assigned_in_body("12"), "|", assigned_in_body("x"))
maybe_bound("4")
maybe_bound("four")
name_unbound()
nums: list[int] = []
strs: list[str] = []
print(first([3, 4], 0), first(nums, 9), first(["a"], "z"), first(strs, "z"))
print(loop_sum(["1", "x", "20", "300", "5"]), loop_sum(["7", "y"]))
print(WIDTH, safe("42"), safe("x"))
try:
    number("1000")
except ArithmeticError as e:
    print("from the module:", repr(e))
