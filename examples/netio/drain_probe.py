"""Exercise fragmented output ownership before the real pipe-consumer check."""

import sys

from drain import Output, drain, remaining


def main() -> None:
    expired = False
    try:
        remaining(-1.0)
    except TimeoutError:
        expired = True
    assert expired
    for count in [0, 1, 255, 256, 257, 768, 769]:
        output = Output()
        for _ in range(count):
            output.append(b"\x00\xffx")
        value = output.value()
        assert output.size == 3 * count
        assert value == b"\x00\xffx" * count
        output.append(b"tail\x00")
        assert value == b"\x00\xffx" * count
        assert output.value() == b"\x00\xffx" * count + b"tail\x00"
    drain([int(value) for value in sys.argv[3:]], float(sys.argv[1]), int(sys.argv[2]))


if __name__ == "__main__":
    main()
