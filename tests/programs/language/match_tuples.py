def pair(value: tuple[int, str]) -> str:
    match value:
        case ():
            return "empty"
        case (1, text) if text:
            return text
        case (_, text):
            return text + "!"
    return "miss"


print(pair((1, "x")), pair((2, "y")), pair((1, "")))


def alternative(value: tuple[int, int]) -> int:
    match value:
        case (0, number) | (number, 0):
            return number
        case pair as whole:
            return pair[0] + whole[1]


print(alternative((0, 4)), alternative((5, 0)), alternative((2, 3)))


def nested(value: tuple[tuple[int, str], int]) -> str:
    match value:
        case ((1,), _):
            return "wrong length"
        case ((1, word), 2):
            return word
        case ((_, word), _):
            return word + "!"
    return "miss"


print(nested(((1, "ok"), 2)), nested(((9, "no"), 4)))


def scalar(value: int) -> str:
    match value:
        case [first, second]:
            return "sequence"
        case _:
            return "scalar"


print(scalar(1))
