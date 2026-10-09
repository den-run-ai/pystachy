import sys

if len(sys.argv) > 5:
    payload = [1, 2]
always = "here"


def count() -> int:
    return len(payload)
