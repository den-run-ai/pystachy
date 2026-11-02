# A user module of the intrinsic helper's name retains ordinary Python behavior.
def scan(data: bytes, start: int, end: int, first: int, second: int, below: int) -> int:
    return len(data) + start + end + first + second + below + 1000
