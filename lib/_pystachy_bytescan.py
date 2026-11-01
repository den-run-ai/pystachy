# pystachy: identity-inert
"""Internal bounded byte scanning shared by native text parsers.

This scalar implementation also runs under CPython. The compiler lowers direct
positional calls of this shipped function to a portable word-at-a-time scanner.
Offsets are bytes, including for UTF-8 input; no decoding or allocation occurs.
This is an implementation helper, not a new method on Python's bytes type.
"""


def scan(data: bytes, start: int, end: int, first: int, second: int, below: int) -> int:
    """First byte equal to either delimiter or less than below; end on no match.

    The half-open range must lie within data, delimiters must be in 0..255, and
    below must be in 0..256. Equal delimiters select one byte; below=0 disables
    the lower-byte test. Bytes with their high bit set are ordinary input.
    """
    if start < 0 or end < start or end > len(data):
        raise IndexError("byte scan out of range")
    if first < 0 or first > 255 or second < 0 or second > 255 or below < 0 or below > 256:
        raise ValueError("invalid byte scan predicate")
    while start < end:
        c = data[start]
        if c == first or c == second or c < below:
            return start
        start += 1
    return end
