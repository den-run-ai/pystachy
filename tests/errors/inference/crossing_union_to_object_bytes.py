# error: in a closed union is not supported
# crossing matrix (tools/crossing_matrix.py), column union_to_object, row bytes: not stored


def pick(v: bytes | int) -> bytes | int:
    return v


def main() -> None:
    x: bytes | int = pick(b'by')
    y: object = x


main()
