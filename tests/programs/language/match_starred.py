# Starred sequence patterns and list subjects (#1305): a list's, runtime-length tuple's or range's
# length is tested where the match runs, a fixed tuple's where it compiles; *rest captures a new
# list of the items between those before and after it, and *_ captures nothing; a dict, set, str
# or scalar subject matches no sequence pattern
def describe(xs: list[int]) -> str:
    match xs:
        case []:
            return "empty"
        case [x]:
            return f"one {x}"
        case [first, *rest]:
            return f"{first} then {rest}"
    return "unreachable"


print(describe([]), describe([7]), describe([1, 2, 3]))


def ends(xs: list[str]) -> str:
    match xs:
        case [first, *middle, last]:
            return f"{first}..{last} around {len(middle)}"
        case [*all_of_them]:
            return f"short {all_of_them}"
    return "unreachable"


print(ends(["a"]), ends(["a", "b"]), ends(["a", "b", "c", "d"]))


def suffix(xs: list[int]) -> int:
    match xs:
        case [*_, 0]:
            return -1
        case [*_, a, b] if a < b:
            return b - a
        case [*front, _]:
            return len(front)
    return 99


print(suffix([5, 0]), suffix([1, 4]), suffix([4, 1]), suffix([3]), suffix([]))


def values(xs: list[int]) -> str:
    match xs:
        case [1, 2, *rest]:
            return f"one-two {rest}"
        case [1, *rest] | [2, *rest]:
            return f"one or two {rest}"
        case [*rest, 9] if rest:
            return f"nine after {rest}"
    return "other"


print(values([1, 2]), values([1, 2, 3]), values([1, 5]), values([2]), values([3, 9]), values([9]))


def fixed(value: tuple[int, int, int]) -> str:
    match value:
        case (0, *rest):
            return f"zero {rest}"
        case (first, *_, last):
            return f"{first} {last}"
    return "unreachable"


print(fixed((0, 1, 2)), fixed((3, 4, 5)))


def no_rest(value: tuple[int, int, int]) -> list[int]:
    match value:
        case (0, 1, 2, *rest):
            rest.append(3)  # (an empty list of the tuple's item type)
            return rest
    return [-1]


print(no_rest((0, 1, 2)), no_rest((1, 1, 2)))


def runtime_length(value: tuple[int, ...]) -> str:
    match value:
        case ():
            return "empty"
        case (x,):
            return f"one {x}"
        case (x, *rest, y):
            return f"{x} {rest} {y}"
    return "unreachable"


print(runtime_length(()), runtime_length((1,)), runtime_length((1, 2)), runtime_length((1, 2, 3, 4)))


def ranged(r: range) -> str:
    match r:
        case []:
            return "empty"
        case [x]:
            return f"one {x}"
        case [first, *rest, last]:
            return f"{first} {rest} {last}"
    return "unreachable"


print(ranged(range(0)), ranged(range(3, 4)), ranged(range(5)), ranged(range(2, 10, 3)))


def mixed(value: tuple[int, str, str]) -> str:
    match value:
        case (n, *words):
            return f"{n} {' '.join(words)}"
    return "unreachable"


print(mixed((2, "a", "b")))


def not_sequences(d: dict[str, int], s: set[int], text: str, n: int) -> list[str]:
    out: list[str] = []
    match d:
        case [*_]:
            out.append("sequence")
        case _:
            out.append("dict is no sequence")
    match s:
        case [*_]:
            out.append("sequence")
        case _:
            out.append("set is no sequence")
    match text:
        case [*chars]:
            out.append(f"chars {chars}")
        case _:
            out.append("str is no sequence here")
    match n:
        case [*_]:
            out.append("sequence")
        case _:
            out.append("scalar")
    return out


print(not_sequences({"a": 1}, {1}, "ab", 3))


def captured_once(xs: list[int]) -> list[int]:
    match xs:
        case [*rest] if len(rest) > 1:
            rest.append(0)  # (a new list: the subject is unchanged)
            return rest
    return []


data = [1, 2]
print(captured_once(data), data)
