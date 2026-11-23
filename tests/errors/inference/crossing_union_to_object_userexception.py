# error: in a closed union is not supported
# crossing matrix (tools/crossing_matrix.py), column union_to_object, row userexception: not stored


class Oops(Exception):
    def describe(self) -> str:
        return "Oops " + str(self)


def pick(v: Oops | int) -> Oops | int:
    return v


def main() -> None:
    x: Oops | int = pick(Oops('bad'))
    y: object = x


main()
