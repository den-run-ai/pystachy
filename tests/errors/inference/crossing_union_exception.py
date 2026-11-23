# error: in a closed union is not supported
# crossing matrix (tools/crossing_matrix.py), column union, row exception: not stored


def pick(v: ValueError | int) -> ValueError | int:
    return v


def main() -> None:
    x: ValueError | int = pick(ValueError('bad'))


main()
