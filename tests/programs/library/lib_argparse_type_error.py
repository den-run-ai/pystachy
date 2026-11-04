import argparse
from argparse import ArgumentTypeError


def positive(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise ArgumentTypeError("expected a positive integer")
    return value


for token in ["7", "0", "x"]:
    try:
        print(positive(token))
    except argparse.ArgumentTypeError as error:
        print(type(error).__name__, str(error))
    except ValueError:
        print("invalid integer")
