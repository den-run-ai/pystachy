# error: in a closed union is not supported
# crossing matrix (tools/crossing_matrix.py), column union_to_object, row exception: not stored


def pick(v: ValueError | int) -> ValueError | int:
    return v


def main() -> None:
    x: ValueError | int = pick(ValueError('bad'))
    y: object = x


main()
